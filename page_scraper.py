import requests
from bs4 import BeautifulSoup
import json
import time
from datetime import datetime, timedelta
from urllib.parse import urljoin, parse_qs, urlparse
import re
import os

class CostaRicaJobsScraper:
    def __init__(self):
        self.base_url = "https://empleos.net"
        self.search_url = "https://empleos.net/buscar_vacantes.php"
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        
    def get_job_listings_page(self, page=1):
        """Get job listings from a specific page"""
        params = {
            'Claves': '',
            'Area': '',
            'Pais': '1',  # Costa Rica
            'page': page
        }
        
        try:
            print(f"Fetching page {page}...")
            response = self.session.get(self.search_url, params=params, timeout=30)
            response.raise_for_status()
            time.sleep(2)  # Slow website - be respectful
            return response.text
        except Exception as e:
            print(f"Error fetching page {page}: {e}")
            return None
    
    def parse_job_listing(self, job_element):
        """Extract job URL from listing page"""
        try:
            # Find the job title link
            title_link = job_element.find('a', href=re.compile(r'puesto/'))
            if title_link:
                job_url = urljoin(self.base_url, title_link['href'])
                return job_url
        except Exception as e:
            print(f"Error parsing job listing: {e}")
        return None
    
    def get_job_details(self, job_url):
        """Scrape detailed job information from individual job page"""
        try:
            print(f"Fetching job details: {job_url}")
            response = self.session.get(job_url, timeout=30)
            response.raise_for_status()
            time.sleep(2)  # Be respectful to the server
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Extract location first as it's used for address and map_location
            location_value = self.extract_location(soup)
            
            job_data = {
                '_job_featured_image': self.extract_featured_image(soup),
                '_job_title': self.extract_title(soup),
                '_job_featured': self.is_featured(soup),
                '_job_filled': 0,  # Default
                '_job_urgent': self.is_urgent(soup),
                '_job_description': self.extract_description(soup),
                '_job_category': self.extract_category(soup),
                '_job_type': self.extract_type(soup),
                '_job_tag': self.extract_tags(soup),
                '_job_expiry_date': self.calculate_expiry_date(),
                '_job_gender': self.extract_gender(soup),
                '_job_apply_type': 'external',
                '_job_apply_url': job_url,
                '_job_apply_email': self.extract_email(soup),
                '_job_salary_type': self.extract_salary_type(soup),
                '_job_salary': self.extract_salary(soup),
                '_job_max_salary': self.extract_max_salary(soup),
                '_job_experience': self.extract_experience(soup),
                '_job_career_level': self.extract_career_level(soup),
                '_job_qualification': self.extract_qualification(soup),
                '_job_video_url': self.extract_video(soup),
                '_job_photos': self.extract_photos(soup),
                '_job_application_deadline_date': self.extract_deadline(soup),
                '_job_address': location_value,
                '_job_location': location_value,
                '_job_map_location': location_value
            }
            
            return job_data
            
        except Exception as e:
            print(f"Error getting job details from {job_url}: {e}")
            return None
    
    def extract_featured_image(self, soup):
        """Extract company logo or featured image"""
        img = soup.find('img', class_=re.compile(r'logo|company'))
        if img and img.get('src'):
            return urljoin(self.base_url, img['src'])
        return ''
    
    def extract_title(self, soup):
        """Extract job title"""
        # First try to find the main heading with the job title (e.g., "Miscelánea")
        # Look for h1, h2, or specific job title patterns
        title_candidates = []
        
        # Try h1, h2 tags first
        for heading in soup.find_all(['h1', 'h2', 'h3']):
            text = heading.get_text(strip=True)
            # Remove badges like "Vacante Fresca"
            text = re.sub(r'Vacante\s+Fresca', '', text, flags=re.IGNORECASE).strip()
            if text and len(text) > 2:
                title_candidates.append(text)
        
        # The job title is usually the first significant heading
        if title_candidates:
            return title_candidates[0]
        
        # Fallback: look for class patterns
        title = soup.find(class_=re.compile(r'title|puesto|job-title'))
        if title:
            text = title.get_text(strip=True)
            text = re.sub(r'Vacante\s+Fresca', '', text, flags=re.IGNORECASE)
            return text.strip()
        
        return ''
    
    def is_featured(self, soup):
        """Check if job is featured - returns 1 or 0"""
        featured_badge = soup.find(class_=re.compile(r'featured|destacado', re.IGNORECASE))
        return 1 if featured_badge is not None else 0
    
    def is_urgent(self, soup):
        """Check if job is urgent - returns 1 or 0"""
        urgent_badge = soup.find(text=re.compile(r'Vacante\s+Fresca|Urgente', re.IGNORECASE))
        return 1 if urgent_badge is not None else 0
    
    def extract_description(self, soup):
        """Extract job description"""
        # Look for description section
        desc_section = soup.find(text=re.compile(r'Funciones del Puesto|Descripción'))
        if desc_section:
            parent = desc_section.find_parent()
            if parent:
                # Get all text from the description area
                desc_div = parent.find_next_sibling() or parent.parent
                if desc_div:
                    return desc_div.get_text(separator='\n', strip=True)
        
        # Fallback: look for common description classes
        desc = soup.find(class_=re.compile(r'description|funciones|contenido'))
        if desc:
            return desc.get_text(separator='\n', strip=True)
        return ''
    
    def extract_category(self, soup):
        """Extract job category/area (in Spanish)"""
        # Look for "Área del Puesto" or similar
        area_label = soup.find(text=re.compile(r'Área del Puesto|Category', re.IGNORECASE))
        if area_label:
            parent = area_label.find_parent()
            if parent:
                value = parent.find_next_sibling() or parent.find_next()
                if value:
                    return value.get_text(strip=True)
        return 'Aduanas'  # Default from the example
    
    def extract_type(self, soup):
        """Extract job type (in Spanish)"""
        # Look for employment type
        type_text = soup.find(text=re.compile(r'Tiempo Completo|Tiempo Parcial|Full[-\s]?Time|Part[-\s]?Time', re.IGNORECASE))
        if type_text:
            text = type_text.get_text(strip=True) if hasattr(type_text, 'get_text') else str(type_text)
            text_lower = text.lower()
            if 'completo' in text_lower or 'full' in text_lower:
                return 'Tiempo Completo'
            elif 'parcial' in text_lower or 'medio' in text_lower or 'part' in text_lower:
                return 'Tiempo Parcial'
        return 'Tiempo Completo'  # Default
    
    def extract_tags(self, soup):
        """Extract job tags"""
        tags = []
        # Look for icons or badges that might indicate tags
        icons = soup.find_all('img', src=re.compile(r'icon|tag'))
        for icon in icons:
            alt_text = icon.get('alt', '').strip()
            if alt_text:
                tags.append(alt_text)
        return ','.join(tags) if tags else ''
    
    def calculate_expiry_date(self):
        """Calculate expiry date (3 months from now)"""
        expiry = datetime.now() + timedelta(days=90)
        return expiry.strftime('%Y-%m-%d')
    
    def extract_gender(self, soup):
        """Extract gender requirement (in Spanish)"""
        gender_text = soup.find(text=re.compile(r'Género|Gender|Sexo', re.IGNORECASE))
        if gender_text:
            parent = gender_text.find_parent()
            if parent:
                value = parent.find_next_sibling() or parent.find_next()
                if value:
                    text = value.get_text(strip=True).lower()
                    if 'masculino' in text or 'hombre' in text or 'male' in text:
                        return 'Masculino'
                    elif 'femenino' in text or 'mujer' in text or 'female' in text:
                        return 'Femenino'
                    elif 'indistinto' in text or 'ambos' in text or 'both' in text:
                        return 'Indistinto'
        return 'Indistinto'
    
    def extract_email(self, soup):
        """Extract application email"""
        # Look for email addresses
        email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
        emails = re.findall(email_pattern, soup.get_text())
        return emails[0] if emails else ''
    
    def extract_salary_type(self, soup):
        """Extract salary type (in Spanish)"""
        salary_text = soup.find(text=re.compile(r'Salario|Salary|Sueldo', re.IGNORECASE))
        if salary_text:
            text = str(salary_text.parent.get_text(strip=True)).lower()
            if 'mensual' in text or 'monthly' in text or 'mes' in text:
                return 'Mensual'
            elif 'anual' in text or 'yearly' in text or 'año' in text:
                return 'Anual'
            elif 'hora' in text or 'hourly' in text:
                return 'Por Hora'
            elif 'semanal' in text or 'weekly' in text or 'semana' in text:
                return 'Semanal'
        return 'Mensual'
    
    def extract_salary(self, soup):
        """Extract minimum salary"""
        salary_text = soup.find(text=re.compile(r'Salario|Salary|Sueldo', re.IGNORECASE))
        if salary_text:
            parent = salary_text.find_parent()
            if parent:
                text = parent.get_text()
                # Look for numbers
                numbers = re.findall(r'\d+[\d,\.]*', text)
                if numbers:
                    return numbers[0].replace(',', '').replace('.', '')
        return ''
    
    def extract_max_salary(self, soup):
        """Extract maximum salary"""
        salary_text = soup.find(text=re.compile(r'Salario|Salary|Sueldo', re.IGNORECASE))
        if salary_text:
            parent = salary_text.find_parent()
            if parent:
                text = parent.get_text()
                # Look for salary range (e.g., "1000 - 2000")
                numbers = re.findall(r'\d+[\d,\.]*', text)
                if len(numbers) >= 2:
                    return numbers[1].replace(',', '').replace('.', '')
        return ''
    
    def extract_experience(self, soup):
        """Extract experience requirement"""
        exp_text = soup.find(text=re.compile(r'Experiencia|Experience', re.IGNORECASE))
        if exp_text:
            parent = exp_text.find_parent()
            if parent:
                value = parent.find_next_sibling() or parent.find_next()
                if value:
                    return value.get_text(strip=True)
        return ''
    
    def extract_career_level(self, soup):
        """Extract career level (in Spanish)"""
        # Look for "Nivel de Cómputo" or career level
        level_text = soup.find(text=re.compile(r'Nivel de Cómputo|Career Level|Nivel', re.IGNORECASE))
        if level_text:
            parent = level_text.find_parent()
            if parent:
                value = parent.find_next_sibling() or parent.find_next()
                if value:
                    text = value.get_text(strip=True)
                    # Keep it in Spanish as found
                    if text:
                        return text
        return 'Nivel Básico'
    
    def extract_qualification(self, soup):
        """Extract qualification/education requirement"""
        qual_text = soup.find(text=re.compile(r'Nivel Académico|Education|Qualification|Escolaridad', re.IGNORECASE))
        if qual_text:
            parent = qual_text.find_parent()
            if parent:
                value = parent.find_next_sibling() or parent.find_next()
                if value:
                    return value.get_text(strip=True)
        return ''
    
    def extract_video(self, soup):
        """Extract video URL if present"""
        video = soup.find('iframe', src=re.compile(r'youtube|vimeo', re.IGNORECASE))
        if video:
            return video['src']
        return ''
    
    def extract_photos(self, soup):
        """Extract additional photos"""
        photos = []
        images = soup.find_all('img')
        for img in images:
            src = img.get('src', '')
            if src and 'logo' not in src.lower() and 'icon' not in src.lower():
                photos.append(urljoin(self.base_url, src))
        return ','.join(photos[:5])  # Limit to 5 photos
    
    def extract_deadline(self, soup):
        """Extract application deadline"""
        deadline_text = soup.find(text=re.compile(r'Fecha[\\s]+Límite|Deadline|Cierre', re.IGNORECASE))
        if deadline_text:
            parent = deadline_text.find_parent()
            if parent:
                value = parent.find_next_sibling() or parent.find_next()
                if value:
                    date_text = value.get_text(strip=True)
                    # Try to parse date
                    try:
                        # Handle format: dd/mm/yyyy
                        date_obj = datetime.strptime(date_text, '%d/%m/%Y')
                        return date_obj.strftime('%Y-%m-%d')
                    except:
                        pass
        return self.calculate_expiry_date()
    
    def extract_location(self, soup):
        """Extract location - used for address, location, and map_location"""
        # Look for location in the listing (e.g., "Tibás, Costa Rica")
        location = soup.find(class_=re.compile(r'location|ubicacion'))
        if location:
            loc_text = location.get_text(strip=True)
            if loc_text:
                return loc_text
        
        # Look for "Ubicación del Puesto" section
        loc_label = soup.find(text=re.compile(r'Ubicación del Puesto|Location|Ubicación', re.IGNORECASE))
        if loc_label:
            parent = loc_label.find_parent()
            if parent:
                value = parent.find_next_sibling() or parent.find_next()
                if value:
                    loc_text = value.get_text(strip=True)
                    if loc_text:
                        return loc_text
        
        # Look for location icon elements in job details
        location_icons = soup.find_all('i', class_=re.compile(r'location|map|pin'))
        for icon in location_icons:
            sibling = icon.find_next_sibling()
            if sibling:
                loc_text = sibling.get_text(strip=True)
                if loc_text and len(loc_text) > 3:
                    return loc_text
        
        # Look for text patterns like "Barrio Tournon, Costa Rica" or "Tibás, San Jose, Costa Rica"
        location_pattern = soup.find(text=re.compile(r'[A-Z][a-záéíóúñ]+,\s*(?:San Jose|Costa Rica)', re.IGNORECASE))
        if location_pattern:
            return location_pattern.strip()
        
        return 'Costa Rica'
    
    def scrape_all_pages(self, max_pages=44):
        """Scrape all job listings from all pages"""
        all_jobs = []
        
        for page in range(1, max_pages + 1):
            print(f"\n=== Processing page {page}/{max_pages} ===")
            
            html = self.get_job_listings_page(page)
            if not html:
                print(f"Failed to fetch page {page}, skipping...")
                continue
            
            soup = BeautifulSoup(html, 'html.parser')
            
            # Find all job listings on the page
            job_cards = soup.find_all(class_=re.compile(r'job|vacancy|puesto|oferta'))
            
            # Alternative: find all links to job details
            if not job_cards:
                job_links = soup.find_all('a', href=re.compile(r'/puesto/'))
                job_cards = [link.parent for link in job_links]
            
            print(f"Found {len(job_cards)} job listings on page {page}")
            
            for job_card in job_cards:
                job_url = self.parse_job_listing(job_card)
                if job_url:
                    job_data = self.get_job_details(job_url)
                    if job_data:
                        all_jobs.append(job_data)
                        print(f"✓ Scraped: {job_data['_job_title']}")
                    time.sleep(1)  # Be respectful between requests
            
            # Check if there are more pages
            if not soup.find('a', text=re.compile(r'siguiente|next', re.IGNORECASE)):
                print("No more pages found")
                break
            
            time.sleep(3)  # Longer delay between pages
        
        return all_jobs
    
    def scrape_first_page_only(self):
        """Scrape only the first page (for weekly updates)"""
        print("\n=== Scraping first page only ===")
        return self.scrape_all_pages(max_pages=1)
    
    def save_to_json(self, jobs, filename='costa_rica_jobs.json'):
        """Save scraped jobs to JSON file"""
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(jobs, f, ensure_ascii=False, indent=2)
        print(f"\n✓ Saved {len(jobs)} jobs to {filename}")
    
    def save_to_csv(self, jobs, filename='costa_rica_jobs.csv'):
        """Save scraped jobs to CSV file"""
        import csv
        
        if not jobs:
            print("No jobs to save")
            return
        
        keys = jobs[0].keys()
        with open(filename, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=keys)
            writer.writeheader()
            writer.writerows(jobs)
        print(f"✓ Saved {len(jobs)} jobs to {filename}")


def initial_scrape():
    """Run initial scrape of all 44 pages"""
    scraper = CostaRicaJobsScraper()
    print("Starting initial scrape of all 44 pages...")
    print("This may take a while due to respectful delays...\n")
    
    jobs = scraper.scrape_all_pages(max_pages=44)
    
    if jobs:
        scraper.save_to_json(jobs, 'costa_rica_jobs_full.json')
        scraper.save_to_csv(jobs, 'costa_rica_jobs_full.csv')
        print(f"\n✅ Initial scrape complete! Total jobs: {len(jobs)}")
    else:
        print("\n⚠️ No jobs were scraped")
    
    return jobs


def weekly_update():
    """Run weekly update (first page only)"""
    scraper = CostaRicaJobsScraper()
    print("Running weekly update (first page only)...\n")
    
    jobs = scraper.scrape_first_page_only()
    
    if jobs:
        # Load existing jobs
        existing_jobs = []
        if os.path.exists('costa_rica_jobs_full.json'):
            with open('costa_rica_jobs_full.json', 'r', encoding='utf-8') as f:
                existing_jobs = json.load(f)
        
        # Add new jobs (avoiding duplicates by URL)
        existing_urls = {job['_job_apply_url'] for job in existing_jobs}
        new_jobs = [job for job in jobs if job['_job_apply_url'] not in existing_urls]
        
        if new_jobs:
            existing_jobs.extend(new_jobs)
            scraper.save_to_json(existing_jobs, 'costa_rica_jobs_full.json')
            scraper.save_to_csv(existing_jobs, 'costa_rica_jobs_full.csv')
            print(f"\n✅ Weekly update complete! Added {len(new_jobs)} new jobs")
        else:
            print("\n✅ Weekly update complete! No new jobs found")
    else:
        print("\n⚠️ No jobs were scraped in weekly update")
    
    return jobs


if __name__ == "__main__":
    # Uncomment the appropriate function:
    
    # For initial scrape (all 44 pages):
    initial_scrape()
    
    # For weekly updates (first page only):
    # weekly_update()
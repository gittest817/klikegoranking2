import requests
from bs4 import BeautifulSoup
from lxml import html

def fetch_data(page_number, course_id, reference_id):
    url = 'https://www.klikego.com/types/generic/custo/x.running/findInInscrits.jsp'
    headers = {
        'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
    }
    data = {
        'search': '',
        'ville': '',
        'course': course_id,
        'reference': reference_id,
        'version': 'v6',
        'page': str(page_number)
    }
    response = requests.post(url, headers=headers, data=data)
    return response.text

def extract_runners(html_content):
    soup = BeautifulSoup(html_content, 'html.parser')
    runners = []
    table = soup.find('table', class_='table table-sm table-bordered table-striped')
    
    if not table:
        print("Aucun tableau trouvé dans le contenu HTML.")
        return runners

    rows = table.find_all('tr', class_='mt-1')
    print(f"Nombre de lignes trouvées : {len(rows)}")  # Debug

    for row in rows:
        cells = row.find_all('td')
        if not cells:
            print("Ligne sans cellules.")
            continue
        
        # Vérifier la présence d’un dossard dans la 1ère cellule
        # Un dossard est identifié par un <b> contenant un nombre
        dossard_cell = cells[0]
        dossard_tag = dossard_cell.find('b')
        
        if dossard_tag and dossard_tag.get_text(strip=True).isdigit():
            # On a un dossard numérique, donc le nom est dans la deuxième cellule
            if len(cells) > 1:
                name_cell = cells[1]
            else:
                print("Pas de deuxième cellule pour le nom, alors qu'on a un dossard.")
                continue
        else:
            # Pas de dossard, donc le nom est dans la première cellule
            name_cell = cells[0]

        # Extraire le nom depuis name_cell
        name_divs = name_cell.find_all('div')
        if len(name_divs) > 1:
            full_name = name_divs[1].get_text(strip=True)
            print(f"Nom extrait : {full_name}")
            runners.append(full_name)
        else:
            print("Nom non trouvé dans une ligne.")
    return runners


def parse_link(link):
    """Extract reference ID from the Klikego link."""
    try:
        parts = link.strip('/').split('/')
        reference_id = parts[-1]
        return reference_id
    except IndexError:
        raise ValueError("Invalid Klikego link format")

def fetch_course_options(reference_id):
    """Fetch available course options from the reference page."""
    url = f'https://www.klikego.com/inscrits/{reference_id}'
    response = requests.get(url)
    soup = BeautifulSoup(response.text, 'html.parser')

    # Find the dropdown or list of distances
    options = soup.find_all('option')
    course_options = {}
    for option in options:
        course_options[option.text.strip()] = option['value']

    if not course_options:
        raise ValueError("No course options found on the page.")

    return course_options

def main():
    link = input("Entrez le lien Klikego de la course : ").strip()
    try:
        reference_id = parse_link(link)
    except ValueError as e:
        print(f"Erreur : {e}")
        return

    try:
        course_options = fetch_course_options(reference_id)
    except ValueError as e:
        print(f"Erreur : {e}")
        return

    # Filter to only include race events (no categories or gender filters)
    filtered_options = {name: course_id for name, course_id in course_options.items()
                        if not any(x in name.lower() for x in ["hommes", "femmes", "mixte", "ea", "po", "be", "mi", "ca", "ju", "es", "se", "m0", "m1", "m2", "m3", "m4", "m5", "m6", "m7", "m8", "m9", "m10"])}

    print("\nLes épreuves disponibles sont :")
    for index, (course_name, course_id) in enumerate(filtered_options.items(), start=1):
        print(f"{index}. {course_name}")

    choice = input("Sélectionnez une épreuve en entrant son numéro : ").strip()
    try:
        choice_index = int(choice) - 1
        selected_course_name = list(filtered_options.keys())[choice_index]
        course_id = filtered_options[selected_course_name]
    except (IndexError, ValueError):
        print("Erreur : sélection invalide.")
        return

    print(f"\nVous avez choisi : {selected_course_name}")

    page_number = 0
    all_runners = []
    while True:
        html_content = fetch_data(page_number, course_id, reference_id)
        
        # Affichez une partie du contenu HTML pour inspection
        if page_number == 0:  # Affiche seulement pour la première page
            print("\n=== Debug: HTML brut reçu pour la page 1 ===")
            print(html_content[:1000])  # Affiche les 1000 premiers caractères

        runners = extract_runners(html_content)
        if not runners:  # Si aucun coureur n'est extrait, c'est la fin des données
            break
        all_runners.extend(runners)
        print(f"Runners on page {page_number + 1}: {runners}")
        page_number += 1  # Passer à la page suivante

    # Afficher tous les coureurs récupérés
    print("\nComplete list of runners:")
    for runner in all_runners:
        print(runner)

if __name__ == "__main__":
    main()

import requests
from bs4 import BeautifulSoup
from typing import List, Dict


def parse_link(link: str) -> str:
    """
    Extrait l'identifiant de référence à partir du lien Klikego.
    Exemple : 
      https://www.klikego.com/inscrits/trail-via-agrippa-2025/1609449728320-5
    Doit renvoyer : 1609449728320-5
    """
    try:
        parts = link.strip('/').split('/')
        return parts[-1]
    except IndexError:
        raise ValueError("Format de lien Klikego invalide.")


def fetch_course_options(session: requests.Session, reference_id: str) -> Dict[str, str]:
    """
    Récupère UNIQUEMENT les options de la liste <select id="course"> 
    sur la page de référence.
    """
    url = f'https://www.klikego.com/inscrits/{reference_id}'
    response = session.get(url)
    if response.status_code != 200:
        raise ValueError(f"Erreur HTTP {response.status_code} lors de l'accès à {url}")

    soup = BeautifulSoup(response.text, 'html.parser')

    # On cible le <select id="course">
    course_select = soup.find('select', {'id': 'course'})
    if not course_select:
        raise ValueError("Impossible de trouver la liste d'épreuves (select id='course').")

    # On ne récupère que les <option> dans ce select
    options = course_select.find_all('option')
    course_options = {}
    for option in options:
        text = option.text.strip()
        value = option.get('value', '').strip()
        if text and value:
            course_options[text] = value

    if not course_options:
        raise ValueError("Aucune épreuve trouvée dans le select id='course'.")

    return course_options


def fetch_data(session: requests.Session, page_number: int, course_id: str, reference_id: str) -> str:
    """
    Envoie une requête POST pour récupérer la page de résultats 
    d'une épreuve donnée (course_id) et d'une page donnée (page_number).
    """
    url = 'https://www.klikego.com/types/generic/custo/x.running/findInInscrits.jsp'
    headers = {'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8'}
    data = {
        'search': '',
        'ville': '',
        'course': course_id,
        'reference': reference_id,
        'version': 'v6',
        'page': str(page_number)
    }
    response = session.post(url, headers=headers, data=data)
    if response.status_code != 200:
        print(f"Erreur HTTP {response.status_code} lors de la récupération de la page {page_number+1}")
        return ""
    return response.text


def extract_runners(html_content: str) -> List[str]:
    """
    Analyse le contenu HTML pour extraire la liste des noms des coureurs.
    Renvoie une liste de chaînes (noms).
    """
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html_content, 'html.parser')
    runners = []
    table = soup.find('table', class_='table table-sm table-bordered table-striped')
    if not table:
        print("Aucun tableau trouvé dans le contenu HTML.")
        return runners

    rows = table.find_all('tr', class_='mt-1')
    for row in rows:
        cells = row.find_all('td')
        if not cells:
            continue

        # Vérifier la présence d’un dossard (balise <b> avec un nombre)
        dossard_cell = cells[0]
        dossard_tag = dossard_cell.find('b')

        if dossard_tag and dossard_tag.get_text(strip=True).isdigit():
            # Nom dans la deuxième cellule
            if len(cells) > 1:
                name_cell = cells[1]
            else:
                continue
        else:
            # Nom dans la première cellule
            name_cell = cells[0]

        name_divs = name_cell.find_all('div')
        if len(name_divs) > 1:
            full_name = name_divs[1].get_text(strip=True)
            runners.append(full_name)

    return runners


def main():
    # Demande du lien Klikego
    link = input("Entrez le lien Klikego de la course : ").strip()
    try:
        reference_id = parse_link(link)
    except ValueError as e:
        print(f"Erreur : {e}")
        return

    with requests.Session() as session:
        # Récupérer la liste d'épreuves
        try:
            course_options = fetch_course_options(session, reference_id)
        except ValueError as e:
            print(f"Erreur : {e}")
            return

        print("\nÉpreuves disponibles :")
        for idx, (name, _) in enumerate(course_options.items(), start=1):
            print(f"{idx}. {name}")

        choice = input("\nSélectionnez une épreuve (numéro) : ").strip()
        try:
            choice_idx = int(choice) - 1
            selected_course_name = list(course_options.keys())[choice_idx]
            course_id = course_options[selected_course_name]
        except (ValueError, IndexError):
            print("Sélection invalide.")
            return

        print(f"\nVous avez choisi : {selected_course_name}\n")

        # Boucle sur les pages
        page_number = 0
        all_runners = []
        while True:
            html_content = fetch_data(session, page_number, course_id, reference_id)
            if not html_content:
                break

            runners = extract_runners(html_content)
            if not runners:
                break

            all_runners.extend(runners)
            print(f"Page {page_number+1} : {len(runners)} coureurs récupérés.")
            page_number += 1

        # Affichage final
        print("\nListe complète des coureurs :")
        for runner in all_runners:
            print(runner)


if __name__ == "__main__":
    main()


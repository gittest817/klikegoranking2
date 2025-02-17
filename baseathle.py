import requests
from bs4 import BeautifulSoup
from lxml import etree
import re
import pandas as pd
from tqdm import tqdm
from concurrent.futures import ThreadPoolExecutor, as_completed

def fetch_performance_data(last_name, first_name, min_distance_km, sex_filter=None):
    base_url = "https://bases.athle.fr/asp.net/liste.aspx"
    params = {
        "frmpostback": "true",
        "frmbase": "resultats",
        "frmmode": "1",
        "frmespace": "0",
        "frmsaison": "2024",
        "frmclub": "",
        "frmnom": last_name,
        "frmprenom": first_name,
        "frmsexe": "",
        "frmlicence": "",
        "frmdepartement": "",
        "frmligue": "",
        "frmcomprch": ""
    }

    response = requests.get(base_url, params=params)
    if response.status_code == 200:
        soup = BeautifulSoup(response.content, 'html.parser')
        dom = etree.HTML(str(soup))

        performances = []
        rows = dom.xpath('//*[@id="ctnResultats"]/tr[td]')
        for row in rows:
            course_name = row.xpath('td[5]/text()')
            if course_name:
                course_name = course_name[0].strip().lower()

                if any(trail in course_name for trail in ["trail xxs", "trail xs","trail s", "trail l", "trail xl", "trail m"]):
                    continue

                if 'semi marathon' in course_name:
                    distance_km = 21.0
                elif '1/2' in course_name and 'marathon' in course_name:
                    distance_km = 21.0
                elif 'semi_marathon' in course_name:
                    distance_km = 21.0
                elif 'half marathon' in course_name:
                    distance_km = 21.0
                elif 'marathon' in course_name:
                    distance_km = 42.0
                else:
                    match = re.search(r'(?<!semi )(\d+)\s?km', course_name)
                    if match:
                        distance_km = float(match.group(1))
                    else:
                        distance_km = None

                if distance_km is not None and distance_km < min_distance_km:
                    continue

                time = row.xpath('td[11]//b/text()') or row.xpath('td[11]//u/text()')
                birth_year_data = row.xpath('td[15]/text()')

                if birth_year_data:
                    birth_year_str = birth_year_data[0].split("/")[-1].strip()
                    sex = birth_year_data[0].split("/")[-2][-1].lower()  # Extraire le sexe
                    if sex_filter and sex != sex_filter:
                        continue
                    try:
                        birth_year = int(birth_year_str)
                        if 0 <= birth_year <= 19:
                            birth_year += 2000
                        elif 20 <= birth_year <= 99:
                            birth_year += 1900
                    except ValueError:
                        birth_year = None
                else:
                    birth_year = None
                    sex = None

                if time:
                    time = time[0].strip()
                    hours = minutes = seconds = 0

                    try:
                        if "h" in time and "'" in time and "''" in time:
                            time_parts = re.split("[h'’\"]+", time)
                            if len(time_parts) >= 3:
                                hours = int(time_parts[0])
                                minutes = int(time_parts[1])
                                seconds = int(time_parts[2])
                        elif "'" in time and "''" in time:
                            time_parts = re.split("[\'’\"]+", time)
                            if len(time_parts) >= 2:
                                minutes = int(time_parts[0])
                                seconds = int(time_parts[1])
                        elif "'" in time and not "''" in time:
                            time_parts = time.split("'")
                            if len(time_parts) == 2:
                                minutes = int(time_parts[0])
                                seconds = int(time_parts[1])
                        elif ":" in time:
                            time_parts = time.split(":")
                            if len(time_parts) == 3:
                                hours = int(time_parts[0])
                                minutes = int(time_parts[1])
                                seconds = int(time_parts[2])
                            elif len(time_parts) == 2:
                                minutes = int(time_parts[0])
                                seconds = int(time_parts[1])
                        else:
                            if 'h' in time:
                                time_parts = re.split("[h'’\"]+", time)
                                if len(time_parts) >= 2:
                                    hours = int(time_parts[0])
                                    min_sec_parts = time_parts[1].split("'")
                                    if len(min_sec_parts) == 2:
                                        minutes = int(min_sec_parts[0])
                                        seconds = int(min_sec_parts[1])
                                    else:
                                        minutes = int(min_sec_parts[0])
                                        seconds = 0
                            else:
                                continue

                        total_seconds = hours * 3600 + minutes * 60 + seconds
                        total_hours = total_seconds / 3600

                        if total_hours > 0 and distance_km is not None:
                            speed_kph = distance_km / total_hours
                        else:
                            speed_kph = 0

                        performance = {
                            "course_name": course_name,
                            "distance_km": distance_km,
                            "time": time,
                            "total_seconds": total_seconds,
                            "speed_kph": speed_kph,
                            "birth_year": birth_year,
                            "sex": sex
                        }
                        performances.append(performance)
                    except ValueError:
                        continue
        return performances
    else:
        return None

def get_athlete_performance_threaded(athlete, min_distance_km, sex_filter):
    last_name, first_name = athlete
    performances = fetch_performance_data(last_name, first_name, min_distance_km, sex_filter)
    if performances:
        for performance in performances:
            performance['athlete'] = f"{first_name} {last_name}"
    return performances

def get_athletes_performances(athletes, min_distance_km, sex_filter):
    all_performances = []
    with ThreadPoolExecutor() as executor:
        futures = {executor.submit(get_athlete_performance_threaded, athlete, min_distance_km, sex_filter): athlete for athlete in athletes}
        for future in tqdm(as_completed(futures), total=len(futures), desc="Processing Athletes"):
            performances = future.result()
            if performances:
                all_performances.extend(performances)
    return all_performances

def filter_performances_by_age(performances, min_age, max_age):
    current_year = pd.Timestamp.now().year
    filtered_performances = [
        p for p in performances
        if p['birth_year'] and (current_year - p['birth_year']) >= min_age and (current_year - p['birth_year']) <= max_age
    ]
    return filtered_performances

def calculate_best_performance(performances, speed_threshold):
    best_performances = {}
    for performance in performances:
        athlete = performance['athlete']
        if performance['speed_kph'] < speed_threshold:
            if athlete not in best_performances:
                best_performances[athlete] = performance
            else:
                if performance['speed_kph'] > best_performances[athlete]['speed_kph']:
                    best_performances[athlete] = performance
    return best_performances

def main():
    additional_runners = [
        "Michael Abrahams", "Christophe Agha", "Tom Airault", "Lara Algardy", "Antoine Andre",
        "Laurent Archambault", "Frederique Astier Saintamand", "Franck Aubard", "Loic Audonnet Lassous",
        "Pierre Audouin", "Rachel Authier", "Julien Bacle", "Jerome Barataud", "Monique Barban","luca Mercier", "romain trohel","charline mercier"
    ]

    athletes = [(name.split()[1], name.split()[0]) for name in additional_runners]

    min_distance_km = 5
    speed_threshold = 25

    min_age = int(input("Enter the minimum age for classification: "))
    max_age = int(input("Enter the maximum age for classification: "))

    sex_filter = input("Filter by sex (m for male, f for female, leave blank for both): ").strip().lower()
    if sex_filter not in ['m', 'f', '']:
        print("Invalid input for sex. Defaulting to both.")
        sex_filter = None

    performances = get_athletes_performances(athletes, min_distance_km, sex_filter)

    performances_by_age = filter_performances_by_age(performances, min_age, max_age)

    best_performances_below_threshold = calculate_best_performance(performances_by_age, speed_threshold)

    df_best_performances = pd.DataFrame(best_performances_below_threshold.values())

    if not df_best_performances.empty:
        df_best_performances['Speed (km/h)'] = df_best_performances['speed_kph']

        df_best_performances_sorted = df_best_performances.sort_values(by='Speed (km/h)', ascending=False)

        print("\nBest Performances Below Threshold (Sorted by Speed):")
        print(df_best_performances_sorted.to_string(index=False))

        df_best_performances_sorted.to_csv('best_performances_by_age_and_sex_below_25kph.csv', index=False)

        print("Data exported to 'best_performances_by_age_and_sex_below_25kph.csv'.")
    else:
        print("No performances found below the speed threshold in the specified age and sex filters.")

if __name__ == "__main__":
    main()

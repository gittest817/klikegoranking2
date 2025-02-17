import time
import streamlit as st
from baseathle import get_athletes_performances, calculate_best_performance, filter_performances_by_age
from recup_klikego import parse_link, fetch_course_options, fetch_data, extract_runners
import pandas as pd

def main():
    st.title("Classement des Coureurs")
    st.set_option('client.showErrorDetails', False)
    performances_by_age = 0
    speed_threshold = 0

    st.header("Étape 1 : Entrer le lien Klikego")

    # Deux colonnes : 2/3 pour le texte, 1/3 pour l'image
    col1, col2 = st.columns([2,1])
    with col1:
        link = st.text_input("Entrez le lien Klikego de la course :")
        if st.button("Valider le lien"):
            if not link:
                st.error("Veuillez entrer un lien.")
            else:
                try:
                    reference_id = parse_link(link)
                    st.success("Lien valide !")
                    # Récupérer les options de course
                    course_options = fetch_course_options(reference_id)
                    # Filtrage des options
                    filtered_options = {
                        name: cid
                        for name, cid in course_options.items()
                        if not any(x in name.lower() for x in ["hommes", "femmes", "mixte", "ea", "po", "be", "mi", "ca", "ju", "es", "se", "m0", "m1", "m2", "m3", "m4", "m5", "m6", "m7", "m8", "m9", "m10"])
                    }
                    st.session_state['filtered_options'] = filtered_options
                except ValueError as e:
                    st.error(f"Erreur : {e}")
    with col2:
        st.image("tutolien.png", caption="Exemple d'une URL Klikego à copier/coller")

    if 'filtered_options' in st.session_state:
        st.header("Étape 2 : Sélectionner une épreuve")
        course_names = list(st.session_state['filtered_options'].keys())
        course_ids = list(st.session_state['filtered_options'].values())
        selected_course = st.selectbox("Choisissez une épreuve :", course_names)
        
        if st.button("Valider l'épreuve"):
            selected_index = course_names.index(selected_course)
            st.session_state['selected_course_name'] = selected_course
            st.session_state['course_id'] = course_ids[selected_index]
            st.success(f"Épreuve sélectionnée : {selected_course}")

    if 'selected_course_name' in st.session_state:
        st.header("Étape 3 : Appliquer des filtres")
        min_age = st.number_input("Âge minimum pour le classement :", min_value=0, value=18)
        max_age = st.number_input("Âge maximum pour le classement :", min_value=0, value=100)
        sex_filter = st.selectbox("Filtrer par sexe :", ["Les deux", "Masculin", "Féminin"])

        if st.button("Appliquer les filtres"):
            st.session_state['min_age'] = min_age
            st.session_state['max_age'] = max_age
            st.session_state['sex_filter'] = sex_filter.lower() if sex_filter.lower() in ['masculin', 'féminin'] else ''
            st.success("Filtres appliqués")

    if 'sex_filter' in st.session_state:
        st.header("Étape 4 : Afficher le classement")

        reference_id = parse_link(link)
        course_id = st.session_state['course_id']
        selected_course_name = st.session_state['selected_course_name']
        min_age = st.session_state['min_age']
        max_age = st.session_state['max_age']
        sex_filter = st.session_state['sex_filter']

        # Extraction des coureurs
        page_number = 0
        all_runners = []
        with st.spinner("Récupération des coureurs..."):
            while True:
                html_content = fetch_data(page_number, course_id, reference_id)
                runners = extract_runners(html_content)
                if not runners:
                    break
                all_runners.extend(runners)
                page_number += 1

        if not all_runners:
            st.warning("Aucun coureur trouvé.")
            return

        st.write(f"Nombre total de coureurs récupérés : {len(all_runners)}")

        # Préparer la liste (Nom, Prénom)
        athletes = []
        for runner in all_runners:
            split_name = runner.split()
            if len(split_name) >= 2:
                last_name = split_name[0].strip()
                first_name = " ".join(split_name[1:]).strip()
                athletes.append((last_name, first_name))
            else:
                st.warning(f"Nom mal formaté ignoré : {runner}")

        st.write("Liste des athlètes récupérés :")
        st.write(athletes)

        # Paramètres
        min_distance_km = 5
        speed_threshold = 25

        # Affichage des performances avec barre de progression et temps restant
        with st.spinner("Récupération des performances des athlètes..."):
            progress_bar = st.progress(0)
            time_info = st.empty()
            start_time = time.time()

            total_athletes = len(athletes)
            performances = []
            
            for i, athlete in enumerate(athletes):
                # Traitement d'un athlète
                athlete_perf = get_athletes_performances([athlete], min_distance_km, sex_filter)
                if athlete_perf:
                    performances.extend(athlete_perf)
                
                # Mise à jour de la barre de progression
                progress = (i+1) / total_athletes
                progress_bar.progress(progress)

                # Calcul du temps écoulé et restant estimé
                elapsed = time.time() - start_time
                avg_time_per_athlete = elapsed / (i+1)
                remaining = total_athletes - (i+1)
                est_time_left = avg_time_per_athlete * remaining

                def format_seconds(sec):
                    h = int(sec // 3600)
                    m = int((sec % 3600) // 60)
                    s = int(sec % 60)
                    if h > 0:
                        return f"{h}h {m}min {s}s"
                    elif m > 0:
                        return f"{m}min {s}s"
                    else:
                        return f"{s}s"

                elapsed_str = format_seconds(elapsed)
                est_str = format_seconds(est_time_left)
                time_info.markdown(f"**Temps écoulé :** {elapsed_str} | **Temps restant estimé :** {est_str}")
        
        if not performances:
            st.warning("Aucune performance trouvée pour les athlètes.")
            return

        # Filtrage par âge
        performances_by_age = filter_performances_by_age(performances, min_age, max_age)

        if not performances_by_age:
            st.warning("Aucune performance trouvée dans la tranche d'âge spécifiée.")
            return

        # Calcul des meilleures performances
        best_performances = calculate_best_performance(performances_by_age, speed_threshold)
        df_best_performances = pd.DataFrame(best_performances.values())

        if df_best_performances.empty:
            st.warning("Aucune meilleure performance à afficher.")
            return

        # Ajout de la colonne 'Speed (km/h)'
        df_best_performances['Speed (km/h)'] = df_best_performances['speed_kph']

        # Convertir total_seconds en format h min s
        if 'total_seconds' in df_best_performances.columns:
            def seconds_to_hms(seconds):
                h = seconds // 3600
                m = (seconds % 3600) // 60
                s = seconds % 60
                return f"{h}h {m}min {s}s"
            df_best_performances['Temps'] = df_best_performances['total_seconds'].apply(seconds_to_hms)

        # Renommer les colonnes
        df_best_performances.rename(columns={
            'athlete': 'Nom complet',
            'birth_year': 'date_of_birth'
        }, inplace=True)

        # Définir l'ordre des colonnes
        colonnes_ordre = ['Nom complet', 'date_of_birth', 'sex', 'distance_km', 'Temps', 'Speed (km/h)']

        colonnes_existantes = [col for col in colonnes_ordre if col in df_best_performances.columns]

        if len(colonnes_existantes) < len(colonnes_ordre):
            st.warning("Toutes les colonnes spécifiées n'existent pas dans le DataFrame. Certaines colonnes ne seront pas affichées.")

        df_best_performances_sorted = df_best_performances[colonnes_existantes].sort_values(by='Speed (km/h)', ascending=False)

        st.subheader("Meilleures performances (triées par vitesse) :")
        st.dataframe(df_best_performances_sorted)

        # Optionnel : téléchargement des résultats
        csv = df_best_performances_sorted.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="Télécharger les résultats en CSV",
            data=csv,
            file_name='best_performances_sorted.csv',
            mime='text/csv',
        )

if __name__ == "__main__":
    main()

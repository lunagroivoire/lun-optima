from datetime import datetime
import sqlite3
import folium
import pandas as pd
import streamlit as st
from streamlit_folium import st_folium

# --- 1. CONFIGURATION DE LA BASE DE DONNÉES & UTILISATEURS ---
def init_db():
    conn = sqlite3.connect("lun_optima.db")
    cursor = conn.cursor()
    
    # Table des Utilisateurs / Agents
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS utilisateurs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            password TEXT,
            role_poste TEXT,
            fonction_grade TEXT,
            acces_admin TEXT
        )
    ''')
    
    # Table des Permissions par Agent (Menus autorisés)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS agent_permissions (
            username TEXT,
            menu_name TEXT,
            PRIMARY KEY (username, menu_name)
        )
    ''')
    
    # Insérer le compte admin par défaut si la table est vide
    cursor.execute("SELECT COUNT(*) FROM utilisateurs")
    if cursor.fetchone()[0] == 0:
        cursor.execute("INSERT INTO utilisateurs (username, password, role_poste, fonction_grade, acces_admin) VALUES ('admin', 'admin123', 'Administrateur', 'Ingénieur', 'Administrateur')")
        cursor.execute("INSERT INTO utilisateurs (username, password, role_poste, fonction_grade, acces_admin) VALUES ('agent_korhogo', 'lun2026', 'Agent terrain', 'Technicien', 'Agent')")
        
        # Permissions par défaut pour l'agent korhogo
        default_menus = [
            "📊 Tableau de Bord & Indicateurs",
            "👨‍🌾 Producteurs & Parcelles (GPS)",
            "📦 Collecte & Double Flux",
            "🏭 Unité de Transformation & Rendements",
            "🤝 Clients & Géo-destination",
            "🗺️ Carte Globale des Flux"
        ]
        for m in default_menus:
            cursor.execute("INSERT OR IGNORE INTO agent_permissions (username, menu_name) VALUES ('agent_korhogo', ?)", (m,))
        conn.commit()

    # Table Producteurs & Parcelles
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS producteurs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nom TEXT,
            telephone TEXT,
            village TEXT,
            superficie REAL,
            lat REAL,
            lon REAL,
            saisi_par TEXT,
            date_heure TEXT
        )
    ''')
    
    # Table Collecte & Double Flux
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS recoltes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            producteur_id INTEGER,
            date_recolte TEXT,
            quantite_kg REAL,
            destination_flux TEXT,
            saisi_par TEXT,
            date_heure TEXT,
            FOREIGN KEY (producteur_id) REFERENCES producteurs (id)
        )
    ''')
    
    # Table Usine & Transformation
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS transformation (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date_transfo TEXT,
            graines_entree_kg REAL,
            huile_produite_l REAL,
            tourteau_produit_kg REAL,
            rendement_estime REAL,
            saisi_par TEXT,
            date_heure TEXT
        )
    ''')
    
    # Table Clients & Géo-destination
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS clients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nom_client TEXT,
            type_produit TEXT,
            quantite REAL,
            destination_ville TEXT,
            lat REAL,
            lon REAL,
            saisi_par TEXT,
            date_heure TEXT
        )
    ''')
    conn.commit()
    conn.close()

init_db()

# --- 2. GESTION DE L'AUTHENTIFICATION ---
st.set_page_config(page_title="LUN OPTIMA AGROBIO - Connexion", layout="wide")

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.username = ""
    st.session_state.acces_admin = ""
    st.session_state.role_poste = ""
    st.session_state.fonction_grade = ""

def login_screen():
    st.title("🌱 LUN OPTIMA AGROBIO - Connexion Sécurisée")
    st.markdown("Veuillez vous identifier pour accéder au système de traçabilité.")
    
    with st.form("login_form"):
        username = st.text_input("Nom d'utilisateur")
        password = st.text_input("Mot de passe / Code d'accès", type="password")
        submit = st.form_submit_button("Se connecter")
        
        if submit:
            conn = sqlite3.connect("lun_optima.db")
            cursor = conn.cursor()
            cursor.execute("SELECT username, acces_admin, role_poste, fonction_grade FROM utilisateurs WHERE username = ? AND password = ?", (username, password))
            user = cursor.fetchone()
            conn.close()
            
            if user:
                st.session_state.logged_in = True
                st.session_state.username = user[0]
                st.session_state.acces_admin = user[1]
                st.session_state.role_poste = user[2]
                st.session_state.fonction_grade = user[3]
                st.success(f"Connexion réussie ! Bienvenue {user[0]} ({user[2]} - {user[3]})")
                st.rerun()
            else:
                st.error("Identifiant ou mot de passe incorrect.")

if not st.session_state.logged_in:
    login_screen()
else:
    # --- 3. APPLICATION PRINCIPALE (Utilisateur Authentifié) ---
    st.sidebar.title(f"👤 {st.session_state.username}")
    st.sidebar.markdown(f"**Poste :** {st.session_state.role_poste}")
    st.sidebar.markdown(f"**Grade :** {st.session_state.fonction_grade}")
    
    if st.sidebar.button("Se déconnecter"):
        st.session_state.logged_in = False
        st.session_state.username = ""
        st.session_state.acces_admin = ""
        st.session_state.role_poste = ""
        st.session_state.fonction_grade = ""
        st.rerun()

    st.title("🌱 LUN OPTIMA AGROBIO - Gestion & Traçabilité centralisée")
    
    # Liste de tous les menus disponibles
    all_menus = [
        "📊 Tableau de Bord & Indicateurs",
        "👨‍🌾 Producteurs & Parcelles (GPS)",
        "📦 Collecte & Double Flux",
        "🏭 Unité de Transformation & Rendements",
        "🤝 Clients & Géo-destination",
        "🗺️ Carte Globale des Flux"
    ]
    
    conn = sqlite3.connect("lun_optima.db")
    if st.session_state.acces_admin == "Administrateur":
        menu_options = all_menus + ["⚙️ Gestion des Comptes, Postes & Permissions"]
    else:
        cursor = conn.cursor()
        cursor.execute("SELECT menu_name FROM agent_permissions WHERE username = ?", (st.session_state.username,))
        allowed_rows = cursor.fetchall()
        menu_options = [row[0] for row in allowed_rows]
        if not menu_options:
            menu_options = ["📊 Tableau de Bord & Indicateurs"]

    if not menu_options:
        st.warning("⚠️ Aucun module ne vous est attribué. Veuillez contacter l'administrateur.")
        st.stop()

    menu = st.sidebar.selectbox("Navigation", menu_options)
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # --- ONGLET 1 : TABLEAU DE BORD ---
    if menu == "📊 Tableau de Bord & Indicateurs":
        st.header("Tableau de Bord Stratégique")
        
        df_recoltes = pd.read_sql("SELECT * FROM recoltes", conn)
        df_prods = pd.read_sql("SELECT * FROM producteurs", conn)
        df_transfo = pd.read_sql("SELECT * FROM transformation", conn)
        
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Total Producteurs", len(df_prods))
        total_recolte = df_recoltes['quantite_kg'].sum() if not df_recoltes.empty else 0
        col2.metric("Total Graines Collectées (kg)", f"{total_recolte:,.0f}")
        
        total_transfo_kg = df_transfo['graines_entree_kg'].sum() if not df_transfo.empty else 0
        col3.metric("Graines Transformées (kg)", f"{total_transfo_kg:,.0f}")
        
        if not df_recoltes.empty:
            flux_transformation = df_recoltes[df_recoltes['destination_flux'] == 'Transformation']['quantite_kg'].sum()
            taux_transfo = (flux_transformation / total_recolte) * 100 if total_recolte > 0 else 0
        else:
            taux_transfo = 0.0
            
        col4.metric("Objectif Transformation", f"{taux_transfo:.1f}%", help="Cible stratégique : 100%")
        st.progress(int(taux_transfo) if taux_transfo <= 100 else 100)
        
        st.subheader("🚨 Alertes & État des Stocks")
        stock_brut_disponible = total_recolte - (df_recoltes[df_recoltes['destination_flux'] == 'Vente Brute']['quantite_kg'].sum() if not df_recoltes.empty else 0) - total_transfo_kg
        
        col_a, col_b = st.columns(2)
        with col_a:
            st.info(f"**Stock de Graines Brutes en attente :** {stock_brut_disponible:,.0f} kg")
        with col_b:
            total_huile = df_transfo['huile_produite_l'].sum() if not df_transfo.empty else 0
            st.success(f"**Stock total Huile produite :** {total_huile:,.1f} Litres")

    # --- ONGLET 2 : PRODUCTEURS & PARCELLES ---
    elif menu == "👨‍🌾 Producteurs & Parcelles (GPS)":
        st.header("Enregistrement des Paysans et Parcelles")
        
        with st.form("form_producteur"):
            col1, col2 = st.columns(2)
            with col1:
                nom = st.text_input("Nom et Prénom du Paysan")
                telephone = st.text_input("Numéro de Téléphone")
                village = st.text_input("Village / Zone de production")
            with col2:
                superficie = st.number_input("Superficie de la parcelle (Hectares)", min_value=0.1, step=0.1)
                lat = st.number_input("Latitude GPS", value=9.45, format="%.6f")
                lon = st.number_input("Longitude GPS", value=-5.62, format="%.6f")
                
            submit = st.form_submit_button("Enregistrer le Paysan")
            if submit and nom:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO producteurs (nom, telephone, village, superficie, lat, lon, saisi_par, date_heure) 
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (nom, telephone, village, superficie, lat, lon, st.session_state.username, current_time))
                conn.commit()
                st.success(f"Producteur {nom} enregistré par {st.session_state.username} !")
                st.rerun()

        st.subheader("Liste des Producteurs & Suppression (Admin)")
        df_prods = pd.read_sql("SELECT * FROM producteurs", conn)
        st.dataframe(df_prods)

        if st.session_state.acces_admin == "Administrateur" and not df_prods.empty:
            st.markdown("---")
            st.warning("⚠️ Zone Administrateur : Suppression d'une saisie producteur")
            prod_to_delete = st.selectbox("Sélectionner le producteur à supprimer", df_prods['id'].tolist(), format_func=lambda x: f"ID {x} - {df_prods[df_prods['id']==x]['nom'].values[0]}")
            if st.button("Supprimer ce producteur"):
                cursor = conn.cursor()
                cursor.execute("DELETE FROM producteurs WHERE id = ?", (prod_to_delete,))
                conn.commit()
                st.success("Producteur supprimé avec succès !")
                st.rerun()

    # --- ONGLET 3 : COLLECTE & DOUBLE FLUX ---
    elif menu == "📦 Collecte & Double Flux":
        st.header("Gestion des Récoltes et Orientation des Flux")
        
        df_prods = pd.read_sql("SELECT id, nom, village FROM producteurs", conn)
        
        if df_prods.empty:
            st.warning("Veuillez d'abord enregistrer au moins un producteur.")
        else:
            with st.form("form_recolte"):
                prods_dict = {f"{row['nom']} ({row['village']})": row['id'] for _, row in df_prods.iterrows()}
                selected_prod_label = st.selectbox("Sélectionner le Paysan", list(prods_dict.keys()))
                producteur_id = prods_dict[selected_prod_label]
                
                date_recolte = st.date_input("Date de réception", datetime.today())
                quantite_kg = st.number_input("Quantité de graines (Kg)", min_value=1.0, step=10.0)
                destination_flux = st.selectbox("Destination de la récolte", ["Transformation", "Vente Brute"])
                
                submit_recolte = st.form_submit_button("Valider la Collecte")
                if submit_recolte:
                    cursor = conn.cursor()
                    cursor.execute("""
                        INSERT INTO recoltes (producteur_id, date_recolte, quantite_kg, destination_flux, saisi_par, date_heure) 
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (producteur_id, str(date_recolte), quantite_kg, destination_flux, st.session_state.username, current_time))
                    conn.commit()
                    st.success(f"Collecte enregistrée par {st.session_state.username} !")
                    st.rerun()

            st.subheader("Historique des Collectes & Suppression (Admin)")
            query = '''
                SELECT r.id, p.nom, r.date_recolte, r.quantite_kg, r.destination_flux, r.saisi_par, r.date_heure 
                FROM recoltes r JOIN producteurs p ON r.producteur_id = p.id
            '''
            df_recoltes_hist = pd.read_sql(query, conn)
            st.dataframe(df_recoltes_hist)

            if st.session_state.acces_admin == "Administrateur" and not df_recoltes_hist.empty:
                st.markdown("---")
                st.warning("⚠️ Zone Administrateur : Suppression d'une collecte")
                recolte_to_delete = st.selectbox("Sélectionner la collecte à supprimer (par ID)", df_recoltes_hist['id'].tolist())
                if st.button("Supprimer cette collecte"):
                    cursor = conn.cursor()
                    cursor.execute("DELETE FROM recoltes WHERE id = ?", (recolte_to_delete,))
                    conn.commit()
                    st.success("Collecte supprimée avec succès !")
                    st.rerun()

    # --- ONGLET 4 : UNITÉ DE TRANSFORMATION & RENDEMENTS ---
    elif menu == "🏭 Unité de Transformation & Rendements":
        st.header("Suivi de l'Usine et Calcul des Rendements")
        
        with st.form("form_transfo"):
            date_transfo = st.date_input("Date d'opération en usine", datetime.today())
            graines_entree_kg = st.number_input("Quantité de graines entrées en usine (Kg)", min_value=1.0, step=10.0)
            huile_produite_l = st.number_input("Huile obtenue (Litres)", min_value=0.0, step=1.0)
            tourteau_produit_kg = st.number_input("Tourteaux obtenus (Kg)", min_value=0.0, step=10.0)
            
            submit_transfo = st.form_submit_button("Enregistrer la Transformation")
            if submit_transfo and graines_entree_kg > 0:
                poids_total_fini = huile_produite_l + tourteau_produit_kg
                rendement_estime = (poids_total_fini / graines_entree_kg) * 100
                
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO transformation (date_transfo, graines_entree_kg, huile_produite_l, tourteau_produit_kg, rendement_estime, saisi_par, date_heure) 
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (str(date_transfo), graines_entree_kg, huile_produite_l, tourteau_produit_kg, rendement_estime, st.session_state.username, current_time))
                conn.commit()
                st.success(f"Transformation enregistrée (Rendement : {rendement_estime:.1f}%)")
                st.rerun()

        st.subheader("Historique des Opérations en Usine & Suppression (Admin)")
        df_transfo_hist = pd.read_sql("SELECT * FROM transformation", conn)
        st.dataframe(df_transfo_hist)

        if st.session_state.acces_admin == "Administrateur" and not df_transfo_hist.empty:
            st.markdown("---")
            st.warning("⚠️ Zone Administrateur : Suppression d'une opération de transformation")
            transfo_to_delete = st.selectbox("Sélectionner l'opération à supprimer (par ID)", df_transfo_hist['id'].tolist())
            if st.button("Supprimer cette opération"):
                cursor = conn.cursor()
                cursor.execute("DELETE FROM transformation WHERE id = ?", (transfo_to_delete,))
                conn.commit()
                st.success("Opération supprimée avec succès !")
                st.rerun()

    # --- ONGLET 5 : CLIENTS & GÉO-DESTINATION ---
    elif menu == "🤝 Clients & Géo-destination":
        st.header("Suivi des Ventes et Géo-destination")
        
        with st.form("form_client"):
            nom_client = st.text_input("Nom du Client / Acheteur")
            type_produit = st.selectbox("Type de produit vendu", ["Graines brutes", "Huile", "Tourteau"])
            quantite = st.number_input("Quantité vendue (Kg ou Litres)", min_value=1.0)
            destination_ville = st.text_input("Ville / Lieu de destination")
            lat_c = st.number_input("Latitude de destination", value=9.46, format="%.6f")
            lon_c = st.number_input("Longitude de destination", value=-5.60, format="%.6f")
            
            submit_client = st.form_submit_button("Enregistrer la Vente")
            if submit_client and nom_client:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO clients (nom_client, type_produit, quantite, destination_ville, lat, lon, saisi_par, date_heure) 
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (nom_client, type_produit, quantite, destination_ville, lat_c, lon_c, st.session_state.username, current_time))
                conn.commit()
                st.success(f"Vente enregistrée par {st.session_state.username} !")
                st.rerun()

        st.subheader("Registre des Ventes & Suppression (Admin)")
        df_clients_hist = pd.read_sql("SELECT * FROM clients", conn)
        st.dataframe(df_clients_hist)

        if st.session_state.acces_admin == "Administrateur" and not df_clients_hist.empty:
            st.markdown("---")
            st.warning("⚠️ Zone Administrateur : Suppression d'une vente")
            client_to_delete = st.selectbox("Sélectionner la vente à supprimer (par ID)", df_clients_hist['id'].tolist())
            if st.button("Supprimer cette vente"):
                cursor = conn.cursor()
                cursor.execute("DELETE FROM clients WHERE id = ?", (client_to_delete,))
                conn.commit()
                st.success("Vente supprimée avec succès !")
                st.rerun()

    # --- ONGLET 6 : CARTE GLOBALE DES FLUX ---
    elif menu == "🗺️ Carte Globale des Flux":
        st.header("Cartographie Interactive (Parcelles & Destinations)")
        
        df_prods = pd.read_sql("SELECT * FROM producteurs", conn)
        df_clients = pd.read_sql("SELECT * FROM clients", conn)
        
        m = folium.Map(location=[9.45, -5.62], zoom_start=11)
        
        for _, row in df_prods.iterrows():
            if row['lat'] and row['lon']:
                folium.Marker(
                    [row['lat'], row['lon']],
                    popup=f"<b>Paysan:</b> {row['nom']}<br><b>Saisi par:</b> {row['saisi_par']}<br><b>Heure:</b> {row['date_heure']}",
                    icon=folium.Icon(color="green", icon="leaf", prefix="fa")
                ).add_to(m)
                
        for _, row in df_clients.iterrows():
            if row['lat'] and row['lon']:
                folium.Marker(
                    [row['lat'], row['lon']],
                    popup=f"<b>Client:</b> {row['nom_client']}<br><b>Saisi par:</b> {row['saisi_par']}<br><b>Heure:</b> {row['date_heure']}",
                    icon=folium.Icon(color="blue", icon="shopping-cart", prefix="fa")
                ).add_to(m)
                
        st_folium(m, width=1100, height=500)

    # --- ONGLET 7 : GESTION DES COMPTES, POSTES, PERMISSIONS & RÉINITIALISATION ---
    elif menu == "⚙️ Gestion des Comptes, Postes & Permissions" and st.session_state.acces_admin == "Administrateur":
        st.header("Administration du Personnel & Sécurité des Accès")
        
        # 1. Enrôlement d'un nouvel agent
        with st.form("form_new_agent"):
            st.subheader("🔑 Enrôler un nouvel agent (Poste & Grade)")
            new_user = st.text_input("Nom d'utilisateur (ex: agent_usine_01)")
            new_pass = st.text_input("Mot de passe / Code d'accès initial", type="password")
            
            col_p1, col_p2, col_p3 = st.columns(3)
            with col_p1:
                new_role_poste = st.selectbox("Rôle / Poste", ["Agent terrain", "Agent d'usine", "Agent de stocks"])
            with col_p2:
                new_fonction_grade = st.selectbox("Fonction / Grade", ["Technicien", "Ouvrier", "Ingénieur", "Machiniste", "Analyste"])
            with col_p3:
                new_acces_admin = st.selectbox("Niveau d'accès", ["Agent", "Administrateur"])
            
            st.markdown("**Bande de sélection des modules autorisés :**")
            selected_defaults = []
            for m in all_menus:
                if st.checkbox(m, value=True, key=f"def_{m}"):
                    selected_defaults.append(m)
            
            submit_agent = st.form_submit_button("Enregistrer le collaborateur")
            if submit_agent and new_user and new_pass:
                try:
                    cursor = conn.cursor()
                    cursor.execute("""
                        INSERT INTO utilisateurs (username, password, role_poste, fonction_grade, acces_admin) 
                        VALUES (?, ?, ?, ?, ?)
                    """, (new_user, new_pass, new_role_poste, new_fonction_grade, new_acces_admin))
                    for m in selected_defaults:
                        cursor.execute("INSERT INTO agent_permissions (username, menu_name) VALUES (?, ?)", (new_user, m))
                    conn.commit()
                    st.success(f"Collaborateur {new_user} ({new_role_poste} - {new_fonction_grade}) créé avec succès !")
                    st.rerun()
                except sqlite3.IntegrityError:
                    st.error("Ce nom d'utilisateur existe déjà.")

        st.markdown("---")
        # 2. RÉINITIALISATION DU CODE D'ACCÈS / MOT DE PASSE
        st.subheader("🔄 Réinitialiser le Code d'Accès d'un Agent")
        df_all_users = pd.read_sql("SELECT username, role_poste, fonction_grade FROM utilisateurs", conn)
        
        if not df_all_users.empty:
            with st.form("form_reset_password"):
                user_to_reset = st.selectbox("Sélectionner l'utilisateur dont le code doit être changé", df_all_users['username'].tolist())
                new_reset_pass = st.text_input("Nouveau mot de passe / Code d'accès", type="password")
                
                submit_reset = st.form_submit_button("Changer le code d'accès")
                if submit_reset:
                    if new_reset_pass.strip() != "":
                        cursor = conn.cursor()
                        cursor.execute("UPDATE utilisateurs SET password = ? WHERE username = ?", (new_reset_pass, user_to_reset))
                        conn.commit()
                        st.success(f"✅ Le code d'accès de l'utilisateur **{user_to_reset}** a été réinitialisé avec succès !")
                    else:
                        st.error("Le nouveau mot de passe ne peut pas être vide.")

        st.markdown("---")
        # 3. Modification des permissions de modules
        st.subheader("⚙️ Modifier les restrictions / permissions d'un agent")
        df_agents = pd.read_sql("SELECT username FROM utilisateurs WHERE acces_admin != 'Administrateur'", conn)
        
        if not df_agents.empty:
            target_agent = st.selectbox("Sélectionner l'agent à restreindre", df_agents['username'].tolist())
            
            cursor = conn.cursor()
            cursor.execute("SELECT menu_name FROM agent_permissions WHERE username = ?", (target_agent,))
            current_perms = [row[0] for row in cursor.fetchall()]
            
            with st.form("form_update_perms"):
                st.markdown(f"**Restreindre / Modifier la bande d'accès pour : `{target_agent}`**")
                new_selected_perms = []
                for m in all_menus:
                    is_checked = m in current_perms
                    if st.checkbox(m, value=is_checked, key=f"perm_{target_agent}_{m}"):
                        new_selected_perms.append(m)
                
                submit_perms = st.form_submit_button("Mettre à jour les accès")
                if submit_perms:
                    cursor.execute("DELETE FROM agent_permissions WHERE username = ?", (target_agent,))
                    for m in new_selected_perms:
                        cursor.execute("INSERT INTO agent_permissions (username, menu_name) VALUES (?, ?)", (target_agent, m))
                    conn.commit()
                    st.success(f"Bande de travail mise à jour pour {target_agent} !")

        st.markdown("---")
        # 4. Tableau global & Suppression
        st.subheader("📋 Tableau du Personnel & Suppression de Comptes")
        df_users_full = pd.read_sql("SELECT id, username, role_poste, fonction_grade, acces_admin FROM utilisateurs", conn)
        st.dataframe(df_users_full)

        if not df_users_full.empty:
            user_to_delete = st.selectbox("Sélectionner l'utilisateur à supprimer", df_users_full['id'].tolist(), format_func=lambda x: f"ID {x} - {df_users_full[df_users_full['id']==x]['username'].values[0]}")
            if st.button("Supprimer ce compte"):
                target_username = df_users_full[df_users_full['id'] == user_to_delete]['username'].values[0]
                if target_username == st.session_state.username:
                    st.error("Vous ne pouvez pas supprimer votre propre compte administrateur en cours d'utilisation !")
                else:
                    cursor = conn.cursor()
                    cursor.execute("DELETE FROM utilisateurs WHERE username = ?", (target_username,))
                    cursor.execute("DELETE FROM agent_permissions WHERE username = ?", (target_username,))
                    conn.commit()
                    st.success(f"Le compte {target_username} a été supprimé.")
                    st.rerun()

    conn.close()
import streamlit as st
import pandas as pd
from discovery_engine import search_civic_network, generate_civic_insight
from db_manager import initialize_database, add_user, log_search, get_user_by_name, update_user_profile, \
    save_collaboration, get_saved_collaborations

initialize_database()

# 1. Page Config
st.set_page_config(page_title="CUNY Civic Discovery", layout="wide", page_icon="🏙️")

# Initialize Session State Variables
if 'viewing_map_for' not in st.session_state:
    st.session_state.viewing_map_for = None
if 'history' not in st.session_state:
    st.session_state.history = []
if 'messages' not in st.session_state:
    st.session_state.messages = []

# 2. Styling
st.markdown("""
    <style>
    section[data-testid="stSidebar"] {
        background-color: #ADD8E6; 
        color: #000000; 
    }
    section[data-testid="stSidebar"] h1, section[data-testid="stSidebar"] h2 {
        color: #003366; 
    }
    .onboarding-card {
        background-color: #f8f9fa;
        padding: 2rem;
        border-radius: 10px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        margin-top: 50px;
    }
    </style>
    """, unsafe_allow_html=True)

# ---------------------------------------------------------
# PHASE 1: THE INTAKE SCREEN
# ---------------------------------------------------------
if 'user_profile' not in st.session_state:
    col1, col2, col3 = st.columns([1, 2, 1])

    with col2:
        st.markdown('<div class="onboarding-card">', unsafe_allow_html=True)
        st.title("🤝 Welcome to the INI Network")
        st.write("Join the CUNY-wide civic system to discover cross-campus partnerships.")

        with st.form("intake_form"):
            name = st.text_input("Full Name *")
            campus = st.selectbox(
                "Campus Affiliation *",
                ["Baruch College", "Bronx CC", "Brooklyn College", "New York City College of Technology",
                 "Hostos CC", "Hunter College", "John Jay College", "LaGuardia CC",
                 "Lehman College", "Queens College", "Other"],
                index=None,
                placeholder="Start typing your campus..."
            )
            role = st.text_input("Role (e.g., Faculty, Student, Admin) (Optional)")
            focus = st.text_input("What is your primary civic focus? (Optional)")
            submitted = st.form_submit_button("Enter the Network")

            if submitted:
                if name and campus:
                    final_focus = focus if focus.strip() else "Discovering Opportunities"
                    existing_user = get_user_by_name(name)

                    if existing_user:
                        # Unpack 6 fields if returning user
                        u_id, u_campus, u_role, u_focus, u_email, u_projects = existing_user
                        st.session_state.user_profile = {
                            "user_id": u_id, "name": name, "campus": u_campus,
                            "role": u_role, "focus": u_focus,
                            "email": u_email if u_email else "",
                            "projects": u_projects if u_projects else ""
                        }
                        greeting = f"Welcome back, {name}! Your AI Copilot is ready on the right."
                    else:
                        user_id = add_user(name, campus, role, final_focus)
                        st.session_state.user_profile = {
                            "user_id": user_id, "name": name, "campus": campus,
                            "role": role, "focus": final_focus,
                            "email": "", "projects": ""
                        }
                        greeting = f"Welcome, {name}! Your AI Copilot is ready to map the network."

                    st.session_state.messages = [{"role": "assistant", "content": greeting}]
                    st.rerun()
                else:
                    st.error("Please fill out your Name and Campus Affiliation to continue.")
        st.markdown('</div>', unsafe_allow_html=True)

# ---------------------------------------------------------
# PHASE 2: THE UNIFIED WORKSPACE (70/30 SPLIT)
# ---------------------------------------------------------
else:
    profile = st.session_state.user_profile

    # --- 1. THE SIDEBAR (Settings & Profile Only) ---
    with st.sidebar:
        st.image("Institute For Nonpartisan Innovation.png", width=200)
        st.title("👤 My Profile")
        st.info(f"**{profile['name']}**\n\n🏫 {profile['campus']}\n\n🎯 {profile['focus']}")

        mode = st.radio("Navigation:", ["🌐 Main Workspace", "⚙️ Edit Profile / Saved"])

    # --- LOAD DATABASE ---
    import sqlite3

    conn = sqlite3.connect('cuny_civic_network.db')
    df = pd.read_sql_query("SELECT * FROM Network_Contacts", conn)
    conn.close()

    # --- PROFILE SETTINGS MODE ---
    if mode == "⚙️ Edit Profile / Saved":
        st.subheader("⚙️ Edit Profile & Saved Contacts")

        tab1, tab2 = st.tabs(["Update Info", "⭐ Saved Collaborations"])

        with tab1:
            with st.form("profile_update_form"):
                new_email = st.text_input("Email Address", value=profile.get('email', ''))
                campuses = ["Baruch College", "Bronx CC", "Brooklyn College", "New York City College of Technology",
                            "Hostos CC", "Hunter College", "John Jay College", "LaGuardia CC", "Lehman College",
                            "Queens College", "Other"]
                current_campus = profile.get('campus')
                campus_idx = campuses.index(current_campus) if current_campus in campuses else None

                new_campus = st.selectbox("Campus Affiliation", campuses, index=campus_idx)
                new_role = st.text_input("Role", value=profile.get('role', ''))
                new_focus = st.text_input("Primary Civic Focus", value=profile.get('focus', ''))
                new_projects = st.text_area("Current Projects & Challenges", value=profile.get('projects', ''),
                                            height=150)

                if st.form_submit_button("Save Changes"):
                    update_user_profile(profile['user_id'], new_email, new_campus, new_role, new_focus, new_projects)
                    st.session_state.user_profile.update({
                        'email': new_email, 'campus': new_campus, 'role': new_role,
                        'focus': new_focus, 'projects': new_projects
                    })
                    st.success("✅ Profile updated!")
                    st.rerun()

        with tab2:
            try:
                saved_df = get_saved_collaborations(profile['user_id'])
                if not saved_df.empty:
                    for _, row in saved_df.iterrows():
                        st.markdown(f"**{row['Contact Name']}** ({row['Campus']}) - {row['Role/Title']}")
                else:
                    st.write("You haven't saved any contacts yet!")
            except Exception as e:
                st.write("No saved contacts found. Ensure database is updated.")

# --- MAIN WORKSPACE MODE (The 70/30 Split) ---
    else:
        # Create the two main columns
        col_main, col_copilot = st.columns([7, 3], gap="large")

        # ==========================================
        # LEFT PANE: DIRECTORY & MAPS (70%)
        # ==========================================
        with col_main:

            # STATE A: VIEWING THE NETWORK MAP FOR A SPECIFIC PERSON
            if st.session_state.viewing_map_for:
                target_id = st.session_state.viewing_map_for
                target_person = df[df['ID'] == target_id].iloc[0] if not df[df['ID'] == target_id].empty else None

                if st.button("⬅️ Back to Directory"):
                    st.session_state.viewing_map_for = None
                    st.rerun()

                if target_person is not None:
                    # 1. Render the person's full card above the map for context
                    st.subheader(f"🕸️ Network Connections for {target_person.get('Contact Name', 'Unknown')}")
                    with st.container(border=True):
                        st.markdown(f"**{target_person.get('Campus', 'Unknown')}** | {target_person.get('Role/Title', '')}")
                        if pd.notna(target_person.get('Civic Domains')):
                            st.markdown(f"**🎯 Focus:** {target_person['Civic Domains']}")
                        if pd.notna(target_person.get('Program/Org Affiliation')):
                            st.markdown(f"**🏢 Program/Org:** {target_person['Program/Org Affiliation']}")

                    # 2. Map Toggle Switch
                    map_mode = st.radio(
                        "Map View Style:",
                        ["🌐 Ecosystem View (Focus-Centric)", "👤 Direct Network (Person-Centric)"],
                        horizontal=True
                    )

                    with st.spinner("Generating physics map..."):
                        from pyvis.network import Network
                        import streamlit.components.v1 as components

                        net = Network(height='600px', width='100%', bgcolor='#ffffff', font_color='#000000')

                        target_name = str(target_person['Contact Name'])
                        target_campus = str(target_person['Campus'])

                        domains_str = str(target_person['Civic Domains'])
                        domains = [d.strip() for d in domains_str.split(',')] if domains_str != "nan" and domains_str != "None" else []

                        # --- MODE 1: ECOSYSTEM VIEW (The New Default) ---
                        if map_mode == "🌐 Ecosystem View (Focus-Centric)":
                            added_nodes = set()

                            # The Target Person (Massive, distinct color)
                            target_node_id = f"TARGET_{target_id}"
                            net.add_node(target_node_id, label=target_name, color='#FFD700', size=40, title="🌟 CURRENTLY VIEWING 🌟")
                            added_nodes.add(target_node_id)

                            for domain in domains:
                                # Central Domain Nodes
                                if domain not in added_nodes:
                                    net.add_node(domain, label=domain, color='#9C27B0', size=35, title="Civic Focus")
                                    added_nodes.add(domain)

                                # Connect Target to Domain
                                net.add_edge(target_node_id, domain, color='#FFD700', value=3)

                                # Find others sharing this domain
                                pattern = f"(?i){domain}"
                                shared_df = df[df['Civic Domains'].fillna('').str.contains(pattern)].head(20) # Limit to 20 to prevent hairball

                                for _, row in shared_df.fillna("Unknown").iterrows():
                                    if str(row['ID']) != str(target_id):
                                        peer_name = str(row['Contact Name'])
                                        peer_campus = str(row['Campus'])
                                        node_id = f"{peer_name} ({peer_campus})"

                                        hover_text = f"Role: {row.get('Role/Title', 'N/A')}\nCapabilities: {row.get('Capabilities / Expertise', 'N/A')}"

                                        # Add Peer Node
                                        if node_id not in added_nodes:
                                            net.add_node(node_id, label=peer_name, color='#2196F3', size=15, title=hover_text)
                                            added_nodes.add(node_id)

                                        # Add Campus Node
                                        if peer_campus not in added_nodes:
                                            net.add_node(peer_campus, label=peer_campus, color='#4CAF50', size=25, title="Campus")
                                            added_nodes.add(peer_campus)

                                        # Link: Domain -> Campus -> Person
                                        net.add_edge(domain, peer_campus, color='#e0e0e0')
                                        net.add_edge(peer_campus, node_id, color='#e0e0e0')

                        # --- MODE 2: DIRECT NETWORK (The Old View) ---
                        else:
                            net.add_node(target_name, label=target_name, color='#FF5722', size=35, title="Focus Contact")
                            net.add_node(target_campus, label=target_campus, color='#4CAF50', size=25, title="Home Campus")
                            net.add_edge(target_name, target_campus, color='#cccccc')

                            for domain in domains:
                                net.add_node(domain, label=domain, color='#9C27B0', size=20)
                                net.add_edge(target_name, domain, color='#cccccc')

                                pattern = f"(?i){domain}"
                                shared_df = df[df['Civic Domains'].fillna('').str.contains(pattern)].head(15)

                                for _, row in shared_df.fillna("Unknown").iterrows():
                                    if row['ID'] != target_id:
                                        peer_name = str(row['Contact Name'])
                                        node_id = f"{peer_name} ({row['Campus']})"
                                        hover_text = f"Role: {row.get('Role/Title', 'N/A')}\nCapabilities: {row.get('Capabilities / Expertise', 'N/A')}"
                                        net.add_node(node_id, label=peer_name, color='#2196F3', size=15, title=hover_text)
                                        net.add_edge(domain, node_id, color='#e0e0e0')

                        # Generate Map
                        net.repulsion(node_distance=150, central_gravity=0.05, spring_length=150, spring_strength=0.05)
                        try:
                            net.save_graph('network_map.html')
                            HtmlFile = open('network_map.html', 'r', encoding='utf-8')
                            components.html(HtmlFile.read(), height=620)
                        except Exception as e:
                            st.error(f"Error generating graph: {e}")

            # STATE B: DIRECTORY BROWSER
            else:
                st.subheader("🗂️ Civic Directory")

                # Filters
                f_col1, f_col2, f_col3, f_col4 = st.columns(4)
                with f_col1:
                    search_name = st.text_input("🔍 Search Name")
                with f_col2:
                    all_campuses = sorted(df['Campus'].dropna().unique().tolist())
                    sel_campuses = st.multiselect("🏫 Campus", all_campuses)
                with f_col3:
                    all_domains = set(item.strip() for d in df['Civic Domains'].dropna() for item in str(d).split(','))
                    sel_domains = st.multiselect("🎯 Focus", sorted(list(all_domains)))
                with f_col4:
                    all_roles = sorted(df['Role/Title'].dropna().unique().tolist())
                    sel_roles = st.multiselect("💼 Role", all_roles)

                # Filter Logic
                filtered_df = df.copy()
                if search_name:
                    filtered_df = filtered_df[
                        filtered_df['Contact Name'].fillna('').str.contains(search_name, case=False)]
                if sel_campuses:
                    filtered_df = filtered_df[filtered_df['Campus'].isin(sel_campuses)]
                if sel_domains:
                    pattern = '|'.join(sel_domains)
                    filtered_df = filtered_df[filtered_df['Civic Domains'].fillna('').str.contains(pattern, case=False)]
                if sel_roles:
                    filtered_df = filtered_df[filtered_df['Role/Title'].isin(sel_roles)]

                st.markdown(f"**Showing {len(filtered_df)} Contacts**")

                # Native Streamlit Container Cards (UPDATED WITH NEW FIELDS)
                for _, row in filtered_df.head(50).iterrows():
                    with st.container(border=True):
                        st.markdown(f"#### {row.get('Contact Name', 'Unknown')}")
                        st.markdown(f"**{row.get('Campus', 'Unknown')}** | {row.get('Role/Title', '')}")

                        if pd.notna(row.get('Program/Org Affiliation')):
                            st.markdown(f"**🏢 Program/Org:** {row['Program/Org Affiliation']}")
                        if pd.notna(row.get('Civic Domains')):
                            st.markdown(f"**🎯 Focus:** {row['Civic Domains']}")
                        if pd.notna(row.get('Capabilities / Expertise')):
                            st.markdown(f"**🛠️ Capabilities:** {row['Capabilities / Expertise']}")
                        if pd.notna(row.get('Communities Served')):
                            st.markdown(f"**👥 Communities Served:** {row['Communities Served']}")
                        if pd.notna(row.get('Email/Phone/LinkedIn')):
                            st.markdown(f"**✉️ Contact:** {row['Email/Phone/LinkedIn']}")

                        if pd.notna(row.get('Notes / Insights')):
                            with st.expander("📝 View Notes & Insights"):
                                st.write(row['Notes / Insights'])

                        # Action Buttons
                        b_col1, b_col2 = st.columns([1, 1])
                        with b_col1:
                            if st.button("⭐ Mark as Interesting", key=f"star_{row['ID']}"):
                                try:
                                    save_collaboration(profile['user_id'], row['ID'])
                                    st.toast(f"Saved {row['Contact Name']} to your list!")
                                except Exception as e:
                                    st.error("Please run the SQL database update first.")
                        with b_col2:
                            if st.button("🗺️ View Connections", key=f"map_{row['ID']}"):
                                st.session_state.viewing_map_for = row['ID']
                                st.rerun()
        # ==========================================
        # RIGHT PANE: THE AI COPILOT (30%)
        # ==========================================
        with col_copilot:
            st.markdown("### 🤖 Civic Copilot")

            search_mode = st.radio(
                "Search Mode",
                ["⚡ Quick Search", "🧠 Deep Search"],
                horizontal=True
            )

            # The Container (fixed height so it doesn't vanish from the screen)
            chat_container = st.container(height=600)

            with chat_container:
                for message in st.session_state.messages:
                    with st.chat_message(message["role"]):
                        st.markdown(message["content"])

            # Chat Input
            if prompt := st.chat_input("Ask Copilot..."):

                # 1. Save and display the user's message instantly
                st.session_state.messages.append({"role": "user", "content": prompt})
                with chat_container:
                    with st.chat_message("user"):
                        st.markdown(prompt)

                # 2. Create the AI's response space
                with chat_container:
                    with st.chat_message("assistant"):
                        # Put the spinner INSIDE the AI's chat bubble
                        with st.spinner("Analyzing..."):
                            try:
                                # We moved log_search here to catch database errors
                                log_search(profile['user_id'], prompt)

                                matches, filters = search_civic_network(prompt, df)

                                if search_mode == "⚡ Quick Search":
                                    if not matches.empty:
                                        insight = generate_civic_insight(prompt, matches)
                                        response = f"{insight}\n\n*(Analyzed {len(matches)} specific entries)*"
                                    else:
                                        response = "I couldn't find enough specific data. Try a broader term or switch to Deep Search."

                                elif search_mode == "🧠 Deep Search":
                                    insight = generate_civic_insight(prompt, df)
                                    response = f"**Deep Insight:**\n\n{insight}\n\n*(Analyzed all {len(df)} entries)*"

                            except Exception as e:
                                # THE MAGIC FIX: If anything crashes, the AI will tell us exactly what it is.
                                response = f"⚠️ **System Error:** {str(e)}"

                        # Render the final response (or the error)
                        st.markdown(response)

                # 3. Save the response to session state so it survives the next reload
                st.session_state.messages.append({"role": "assistant", "content": response})

                if 'history' not in st.session_state:
                    st.session_state.history = []
                st.session_state.history.append(prompt)
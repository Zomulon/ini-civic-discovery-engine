import streamlit as st
import pandas as pd
from discovery_engine import search_civic_network, generate_civic_insight
from db_manager import initialize_database, add_user, log_search, get_user_by_name, update_user_profile, \
    save_collaboration, get_saved_collaborations, publish_user_to_directory

initialize_database()

# The "Bridge": Maps messy CSV shorthand to clean UI names
CUNY_MAP = {
    "BMCC": "Borough of Manhattan Community College",
    "Baruch College": "Baruch College",
    "Bronx Community College": "Bronx Community College",
    "Brooklyn College": "Brooklyn College",
    "City College": "The City College of New York",
    "College of Staten Island": "College of Staten Island",
    "Graduate Center": "CUNY Graduate Center",
    "Guttman Community College": "Guttman Community College",
    "Hostos Community College": "Hostos Community College",
    "Hunter College": "Hunter College",
    "John Jay College": "John Jay College of Criminal Justice",
    "Kingsborough CC": "Kingsborough Community College",
    "Kingsborough Community College": "Kingsborough Community College",
    "LaGuardia CC": "LaGuardia Community College",
    "Lehman College": "Lehman College",
    "Macaulay Honors": "Macaulay Honors College",
    "Medgar Evers": "Medgar Evers College",
    "Medgar Evers College": "Medgar Evers College",
    "NYC College of Technology": "New York City College of Technology",
    "city tech": "New York City College of Technology",
    "Queens College": "Queens College",
    "Queensborough CC": "Queensborough Community College",
    "York College": "York College",
    "CUNY Law School": "CUNY School of Law",
    "CUNY SPS": "CUNY School of Professional Studies",
    "School of Public Health": "CUNY Graduate School of Public Health & Health Policy",
    "School of Labor & Urban Studies": "CUNY School of Labor and Urban Studies",
    "Craig Newmark Graduate School of Journalism": "Craig Newmark Graduate School of Journalism at CUNY",
}


CUNY_COLLEGES = sorted(list(set(CUNY_MAP.values())))

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
                CUNY_COLLEGES,
                index=None,
                placeholder="Select or type your campus..."
            )
            ROLE_BUCKETS = ["Faculty & Teachers", "Students & Fellows", "Administration", "External Partners", "INI Staff"]
            role = st.selectbox(
                "Role Category (Optional)",
                ROLE_BUCKETS,
                index=None,
                placeholder="Select your role..."
            )
            FOCUS_BUCKETS = [
                "Education & Youth Development", "Justice, Policy & Government",
                "Health & Wellness", "Community & Civic Engagement",
                "Economic Empowerment & Workforce", "Arts, Media & Culture",
                "Environment & Sustainability", "Technology, Data & Innovation",
                "Research & Social Sciences", "Other / Cross-Cutting"
            ]
            focus = st.selectbox("Primary Civic Focus (Optional)", FOCUS_BUCKETS, index=None, placeholder="Select your focus...")
            submitted = st.form_submit_button("Enter the Network")

            if submitted:
                if name and campus:
                    final_focus = focus if focus else "Discovering Opportunities"
                    existing_user = get_user_by_name(name)

                    if existing_user:
                        # Unpack 7 fields if returning user
                        u_id, u_campus, u_role, u_focus, u_email, u_projects, u_linked_id = existing_user
                        st.session_state.user_profile = {
                            "user_id": u_id, "name": name, "campus": u_campus,
                            "role": u_role, "focus": u_focus,
                            "email": u_email if u_email else "",
                            "projects": u_projects if u_projects else "",
                            "linked_contact_id": u_linked_id
                        }
                        greeting = f"Welcome back, {name}! Your AI Copilot is ready on the \"Ask copilot"\" text below."
                    else:
                        user_id = add_user(name, campus, role, final_focus)
                        st.session_state.user_profile = {
                            "user_id": user_id, "name": name, "campus": campus,
                            "role": role, "focus": final_focus,
                            "email": "", "projects": "", "linked_contact_id": None
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
                campuses = CUNY_COLLEGES
                current_campus = profile.get('campus')
                # Find index of current campus to set as default
                campus_idx = CUNY_COLLEGES.index(current_campus) if current_campus in CUNY_COLLEGES else None

                new_campus = st.selectbox("Campus Affiliation", CUNY_COLLEGES, index=campus_idx)
                ROLE_BUCKETS = ["Faculty & Teachers", "Students & Fellows", "Administration", "External Partners",
                                "INI Staff"]
                current_role = profile.get('role')
                # Find their saved role in the list, otherwise leave it blank
                role_idx = ROLE_BUCKETS.index(current_role) if current_role in ROLE_BUCKETS else None

                new_role = st.selectbox("Role Category", ROLE_BUCKETS, index=role_idx)

                FOCUS_BUCKETS = ["Education & Youth", "Justice & Policy", "Health & Wellness", "Environment & Sustainability", "Economic Empowerment", "Arts & Culture", "Community Building"]
                current_focus = profile.get('focus')
                focus_idx = FOCUS_BUCKETS.index(current_focus) if current_focus in FOCUS_BUCKETS else None
                new_focus = st.selectbox("Primary Civic Focus", FOCUS_BUCKETS, index=focus_idx)

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

            # THE NEW PUBLISH BUTTON
            st.markdown("---")
            st.subheader("🌍 Public Directory")
            st.write("Publish your profile to the public network so others can find your card and see your map connections. (Make sure you 'Save Changes' above first!)")
            if st.button("🚀 Publish My Profile to Directory"):
                publish_user_to_directory(profile['user_id'], st.session_state.user_profile)
                st.success("🎉 You are now live in the Public Directory! Your card and ecosystem map are visible to the network.")
                st.balloons()

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

                    st.markdown(
                        "**Map Key:** 🟡 **Target Contact** | 🟣 **Civic Focus** | 🟢 **Location** | 🔵 **Shared Connection**")

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

                # --- THE WELCOME EXPANDER ---
                with st.expander("👋 How to use this workspace (and why it matters)"):
                    st.markdown("""
                    **Welcome to the CUNY Civic Discovery Network!** This tool was built in partnership with the **Institute for Nonpartisan Innovation (INI)** to break down silos across the CUNY system and foster powerful cross-campus collaborations. 
                    
                    **How to get the most out of the platform:**
                    * 🔍 **Find Partners:** Use the filters below to discover faculty, students, and organizations working in your specific civic domain.
                    * 🕸️ **Map the Ecosystem:** Click "🗺️ View Connections" on any contact card to generate a visual web of how they connect to other campuses and topics.
                    * 🤖 **Ask the AI:** Use the Civic Copilot on the right to instantly analyze trends, summarize notes, or find highly specific collaborations across the 1,300+ contact database.
                    """)
                # ----------------------------

                # ==========================================
                # THE UPGRADED FILTERS (5 Columns)
                # ==========================================
                f_col1, f_col2, f_col3, f_col4, f_col5 = st.columns(5)

                with f_col1:
                    search_keyword = st.text_input("🔍 Name or Keyword")

                with f_col2:
                    # Logic: If it's in our CUNY_MAP, it's a Campus.
                    all_locations = df['Campus'].dropna().unique().tolist()
                    cuny_only = sorted(list(set([CUNY_MAP[c] for c in all_locations if c in CUNY_MAP])))
                    sel_cuny = st.multiselect("🏫 CUNY Campus", cuny_only)

                with f_col3:
                    # Logic: If it's NOT in our CUNY_MAP, it's a Community Partner.
                    partners_only = sorted([c for c in all_locations if c not in CUNY_MAP])
                    sel_partners = st.multiselect("🌍 Community Partner", partners_only)

                with f_col4:
                    # The Hybrid UI Bucketing Logic for Domains
                    DOMAIN_MAPPINGS = {
                        "Education & Youth Development": r"Education|Youth|School|K-12|Tutoring|College|Student|Academia",
                        "Justice, Policy & Government": r"Justice|\bLaw\b|\bLegal\b|Policy|Advocacy|Voting|Democracy|Rights|Equity|Government|Immigration",
                        "Health & Wellness": r"Health|Medical|Mental Health|Food Security|Nutrition|\bCare\b|Wellness",
                        "Community & Civic Engagement": r"Community|Housing|Urban|Planning|Neighborhood|Civic",
                        "Economic Empowerment & Workforce": r"Economic|Workforce|Jobs|Business|Entrepreneurship|Career",
                        "Arts, Media & Culture": r"\bArt\b|\bArts\b|Culture|Media|Journalism|History|Communications",
                        "Environment & Sustainability": r"Environment|Climate|Sustainability|Energy|Green",
                        "Technology, Data & Innovation": r"Technology|Tech|Data|\bSTEM\b|Innovation|\bIT\b",
                        "Research & Social Sciences": r"Research|Sociology|Political Science|Science|Study",
                        "Other / Cross-Cutting": r"Other|Cross|Interdisciplinary"
                    }
                    sel_domains = st.multiselect("🎯 Focus Area", list(DOMAIN_MAPPINGS.keys()))

                with f_col5:
                    # The Hybrid UI Bucketing Logic
                    ROLE_MAPPINGS = {
                        "Faculty & Teachers": r"Professor|Adjunct|Faculty|Lecturer|Instructor|Teacher",
                        "Students & Fellows": r"Student|Candidate|Fellow|Scholar",
                        "Administration": r"Dean|Director|Provost|President|Coordinator|Manager|Chair|Admin",
                        "External Partners": r"Founder|\bCEO\b|Consultant|Partner",
                        "INI Staff": r"\bINI\b|Vngle"
                    }
                    sel_roles = st.multiselect("💼 Role Category", list(ROLE_MAPPINGS.keys()))

                # ==========================================
                # THE UPGRADED FILTERING LOGIC
                # ==========================================
                filtered_df = df.copy()

                if search_keyword:
                    # Search across Name, Domains, Affiliation, and Notes simultaneously!
                    search_mask = (
                        filtered_df['Contact Name'].fillna('').str.contains(search_keyword, case=False) |
                        filtered_df['Civic Domains'].fillna('').str.contains(search_keyword, case=False) |
                        filtered_df['Notes / Insights'].fillna('').str.contains(search_keyword, case=False) |
                        filtered_df['Program/Org Affiliation'].fillna('').str.contains(search_keyword, case=False)
                    )
                    filtered_df = filtered_df[search_mask]

                # Combine the two location dropdowns
                if sel_cuny or sel_partners:
                    # We need to find all the "raw" names that match the user's "clean" selections
                    raw_targets = []

                    # Add partners directly
                    raw_targets.extend(sel_partners)

                    # Add all raw variations for the selected CUNY schools
                    for raw_name, clean_name in CUNY_MAP.items():
                        if clean_name in sel_cuny:
                            raw_targets.append(raw_name)

                    filtered_df = filtered_df[filtered_df['Campus'].isin(raw_targets)]

                if sel_domains:
                    combined_domain_pattern = '|'.join([DOMAIN_MAPPINGS[d] for d in sel_domains])
                    filtered_df = filtered_df[filtered_df['Civic Domains'].fillna('').str.contains(combined_domain_pattern, case=False, regex=True)]

                if sel_roles:
                    # Combine the regex patterns for the selected buckets and filter the raw text
                    combined_pattern = '|'.join([ROLE_MAPPINGS[role] for role in sel_roles])
                    filtered_df = filtered_df[filtered_df['Role/Title'].fillna('').str.contains(combined_pattern, case=False, regex=True)]

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
            st.caption("💡 **Tip:** Ask questions that mention specific people, topics, or campuses/locations (e.g., *\"Who does food security at Lehman?\"* or *\"Explain Sada Jaman's work?\"*) for fast results. "
                       "Open-ended questions will automatically trigger a full-network Deep Search that may take a long time to complete.")



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
                                if not matches.empty:
                                    insight = generate_civic_insight(prompt, matches)
                                    response = f"{insight}\n\n*(Analyzed {len(matches)} specific entries)*"
                                else:
                                    st.info("Not enough specific matches. Expanding search to the entire network...")
                                    insight = generate_civic_insight(prompt, df)
                                    response = f"**Deep Insight (Expanded Search):**\n\n{insight}\n\n*(Analyzed all {len(df)} entries)*"


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

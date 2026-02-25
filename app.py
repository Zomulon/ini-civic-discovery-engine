import streamlit as st
import pandas as pd
from discovery_engine import search_civic_network, generate_civic_insight
from db_manager import initialize_database, add_user, log_search, get_user_by_name

initialize_database()

# 1. Page Config
st.set_page_config(page_title="CUNY Civic Discovery", layout="wide", page_icon="🏙️")

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
    .main .block-container {
        max-width: 900px;
    }
    /* Style for the Onboarding Card */
    .onboarding-card {
        background-color: #f8f9fa;
        padding: 2rem;
        border-radius: 10px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        margin-top: 50px;
    }
    /* Style for the Directory Contact Cards */
    .contact-card {
        background-color: #ffffff;
        padding: 1.5rem;
        border-radius: 8px;
        border: 1px solid #e0e0e0;
        margin-bottom: 1rem;
        box-shadow: 2px 2px 5px rgba(0,0,0,0.05);
    }
    </style>
    """, unsafe_allow_html=True)

# ---------------------------------------------------------
# PHASE 1: THE INTAKE SCREEN
# ---------------------------------------------------------
explanation = """
**How to use:**
1. Use the **left sidebar** to switch between *Partner Search* and *Chat Mode*.
2. **Partner Search:** Find contacts (e.g., 'Who is working in public health?' or just 'public health').
3. **Chat Mode:** Get deep details on a contact (e.g., 'Explain Liz Evans' work').
"""
if 'user_profile' not in st.session_state:
    # Use columns to center the form on the screen
    col1, col2, col3 = st.columns([1, 2, 1])

    with col2:
        st.markdown('<div class="onboarding-card">', unsafe_allow_html=True)
        st.title("🤝 Welcome to the INI Network")
        st.write("Join the CUNY-wide civic system to discover cross-campus partnerships.")

        # The Form
        with st.form("intake_form"):
            name = st.text_input("Full Name *")

            # The Searchable Dropdown
            # index=None forces it to be empty until the user types or clicks
            campus = st.selectbox(
                "Campus Affiliation * (Type to search)",
                ["Baruch College", "Bronx CC", "Brooklyn College", "New York City College of Technology",
                 "Hostos CC", "Hunter College", "John Jay College", "LaGuardia CC",
                 "Lehman College", "Queens College", "Other"],
                index=None,
                placeholder="Start typing your campus..."
            )

            role = st.text_input("Role (e.g., Faculty, Student, Admin) (Optional)")

            # Made optional
            focus = st.text_input("What is your primary civic focus? (Optional)")

            submitted = st.form_submit_button("Enter the Network")

            if submitted:
                if name and campus:
                    # Default focus if they left it blank
                    final_focus = focus if focus.strip() else "Discovering Opportunities"

                    # --- NEW LOOKUP LOGIC ---
                    existing_user = get_user_by_name(name)

                    if existing_user:
                        # 1. USER EXISTS: Unpack their existing data from the database
                        u_id, u_campus, u_role, u_focus = existing_user

                        st.session_state.user_profile = {
                            "user_id": u_id,
                            "name": name,
                            "campus": u_campus,  # Use the campus they originally registered with
                            "role": u_role,
                            "focus": u_focus
                        }

                        # A slightly different greeting for returning users
                        greeting = f"Welcome back, {name}! Let's continue mapping **{u_focus}**." + explanation

                    else:
                        # 2. NEW USER: Add them to the database
                        user_id = add_user(name, campus, role, final_focus)

                        st.session_state.user_profile = {
                            "user_id": user_id,
                            "name": name,
                            "campus": campus,
                            "role": role,
                            "focus": final_focus
                        }

                        greeting = f"Welcome to the network, {name}! I see your focus is **{final_focus}** at {campus}. How can I help you find partners today?" + explanation

                    # Preload the first chat message
                    st.session_state.messages = [
                        {"role": "assistant", "content": greeting}
                    ]

                    # Reload the app to enter the chat
                    st.rerun()
                else:
                    st.error("Please fill out your Name and Campus Affiliation to continue.")
        st.markdown('</div>', unsafe_allow_html=True)

# ---------------------------------------------------------
# PHASE 2: THE MAIN CHAT INTERFACE
# ---------------------------------------------------------
else:
    # We are in the main app now because 'user_profile' exists!
    profile = st.session_state.user_profile

    # Sidebar
    with st.sidebar:
        st.title("⚙️ Controls")
        st.image("Institute For Nonpartisan Innovation.png", width=200)
        # Display the logged-in user
        st.info(f"👤 **{profile['name']}**\n\n🏫 {profile['campus']}\n\n🎯 {profile['focus']}")
        st.markdown("---")

        mode = st.radio("Interaction Mode:", [
            "🔍 Partner Search",
            "💬 Civic Chat",
            "🗂️ Browse Directory",
            "🕸️ Network Map",
            "🧠 Network Analysis"
        ])
        st.markdown("---")

        st.subheader("📚 History")
        if 'history' not in st.session_state:
            st.session_state.history = []

        for item in st.session_state.history:
            st.caption(f"▫️ {item}")

    # --- LOAD DATABASE FOR ALL MODES ---
    import sqlite3

    conn = sqlite3.connect('cuny_civic_network.db')
    df = pd.read_sql_query("SELECT * FROM Network_Contacts", conn)
    conn.close()

    # ---------------------------------------------------------
    # MODE 3: THE FACETED DIRECTORY
    # ---------------------------------------------------------
    if mode == "🗂️ Browse Directory":
        st.subheader("🗂️ Network Directory")
        st.write("Use the filters on the left to explore the INI ecosystem.")

        # Create the Amazon-like layout: 1 column for filters, 3 for results
        filter_col, results_col = st.columns([1, 3])

        with filter_col:
            st.markdown("### 🎯 Filters")

            # Extract unique campuses for the dropdown
            all_campuses = sorted(df['Campus'].dropna().unique().tolist())
            selected_campuses = st.multiselect("Campus", all_campuses)

            # Extract unique domains (splitting them since they are comma-separated)
            all_domains = set()
            for d in df['Civic Domains'].dropna():
                for item in str(d).split(','):
                    all_domains.add(item.strip())
            selected_domains = st.multiselect("Civic Focus", sorted(list(all_domains)))

            # Extract unique roles
            all_roles = sorted(df['Role/Title'].dropna().unique().tolist())
            selected_roles = st.multiselect("Role / Title", all_roles)

        with results_col:
            filtered_df = df.copy()

            # Apply the filters if the user selected any
            if selected_campuses:
                filtered_df = filtered_df[filtered_df['Campus'].isin(selected_campuses)]
            if selected_domains:
                pattern = '|'.join(selected_domains)
                filtered_df = filtered_df[
                    filtered_df['Civic Domains'].fillna('').str.contains(pattern, case=False)]
            if selected_roles:
                filtered_df = filtered_df[filtered_df['Role/Title'].isin(selected_roles)]

            st.markdown(f"**Showing {len(filtered_df)} Contacts**")

            # Display the cards (Limiting to 50 at a time to keep the app fast)
            for _, row in filtered_df.head(50).iterrows():

                # Safely get the header variables
                name = row.get('Contact Name', 'Unknown Contact')
                campus = row.get('Campus', 'Unknown Campus')
                role = row.get('Role/Title', '')

                # Format the subtitle gracefully if role is missing
                role_text = f" | {role}" if pd.notna(role) and str(role).strip() else ""

                # Start building the HTML card
                card_html = f"""
                            <div class="contact-card">
                                <h4 style="margin-bottom: 0px; color: #003366;">{name}</h4>
                                <p style="margin-top: 0px; color: #666; margin-bottom: 12px; border-bottom: 1px solid #eee; padding-bottom: 8px;">
                                    <strong>{campus}</strong>{role_text}
                                </p>
                            """


                # Helper function to only add a line if data exists
                def add_field(label, value, emoji=""):
                    if pd.notna(value) and str(value).strip() != "" and str(value).strip() != "nan":
                        return f"<p style='margin: 4px 0; font-size: 0.95rem;'><strong>{emoji} {label}:</strong> {value}</p>"
                    return ""


                # Dynamically add all the available fields!
                card_html += add_field("Contact", row.get('Email/Phone/LinkedIn'), "✉️")
                card_html += add_field("Website", row.get('URL (Overview Page)'), "🌐")
                card_html += add_field("Program/Org", row.get('Program/Org Affiliation'), "🏢")
                card_html += add_field("Focus", row.get('Civic Domains'), "🎯")
                card_html += add_field("Capabilities", row.get('Capabilities / Expertise'), "🛠️")
                card_html += add_field("Communities Served", row.get('Communities Served'), "👥")
                card_html += add_field("Needs / Challenges", row.get('Needs / Challenges'), "⚠️")
                card_html += add_field("Notes", row.get('Notes / Insights'), "📝")

                # Close the div
                card_html += "</div>"

                st.markdown(card_html, unsafe_allow_html=True)
                st.markdown(card_html, unsafe_allow_html=True)
        # ---------------------------------------------------------
        # MODE 4: THE INTERACTIVE NETWORK MAP
        # ---------------------------------------------------------
    elif mode == "🕸️ Network Map":
        st.subheader("🕸️ Interactive Network Map")
        st.write(
            "Visualize how civic focus areas connect across different CUNY campuses. Select a focus area to generate the constellation.")

        # 1. Extract unique domains for the dropdown
        all_domains = set()
        for d in df['Civic Domains'].dropna():
            for item in str(d).split(','):
                all_domains.add(item.strip())

        # We use a selectbox to force the user to pick one topic, preventing a 1,300-node browser crash
        selected_domain = st.selectbox("Select a Civic Focus to Map:", sorted(list(all_domains)))

        if selected_domain:
            with st.spinner(f"Mapping the {selected_domain} network..."):
                from pyvis.network import Network
                import streamlit.components.v1 as components

                # Filter data to only people involved in this specific domain
                pattern = f"(?i){selected_domain}"
                filtered_df = df[df['Civic Domains'].fillna('').str.contains(pattern)]

                # Initialize the PyVis Network Graph
                net = Network(height='600px', width='100%', bgcolor='#ffffff', font_color='#000000')

                # Create the Central Node (The Civic Domain itself)
                net.add_node(selected_domain, label=selected_domain, color='#FF5722', size=40, title="Civic Focus Area")

                added_campuses = set()

                # 1. Use .fillna("Unknown") to ensure we don't pass any NaN floats to PyVis
                for _, row in filtered_df.fillna("Unknown").iterrows():

                    # 2. Force everything to be a string just to be extra safe
                    contact_name = str(row['Contact Name'])
                    campus = str(row['Campus'])
                    role = str(row['Role/Title']) if row['Role/Title'] != "Unknown" else "No Role Listed"
                    capabilities = str(row['Capabilities / Expertise']) if row[
                                                                               'Capabilities / Expertise'] != "Unknown" else "None"

                    # 3. Add Campus Node (if it doesn't exist yet)
                    if campus not in added_campuses:
                        net.add_node(campus, label=campus, color='#4CAF50', size=25, title="CUNY Campus")
                        net.add_edge(selected_domain, campus, color='#cccccc')
                        added_campuses.add(campus)

                    # 4. Add the Person Node
                    # We combine Name and Campus for the Node ID to prevent identical names from merging!
                    node_id = f"{contact_name} ({campus})"

                    hover_text = f"Role: {role}\nCapabilities: {capabilities}"

                    # Using node_id for the system, but label for what the user actually sees
                    net.add_node(node_id, label=contact_name, color='#2196F3', size=15, title=hover_text)
                    net.add_edge(campus, node_id, color='#e0e0e0')

                # Turn on the physics engine for the "constellation" floating effect
                net.repulsion(node_distance=120, central_gravity=0.05, spring_length=120, spring_strength=0.05)

                # Save the graph to an HTML file and embed it in Streamlit
                try:
                    net.save_graph('network_map.html')
                    HtmlFile = open('network_map.html', 'r', encoding='utf-8')
                    components.html(HtmlFile.read(), height=620)
                except Exception as e:
                    st.error(f"Error generating graph: {e}")
    # ---------------------------------------------------------
    # MODES 1 & 2: SEARCH AND CHAT
    # ---------------------------------------------------------
    else:
        # Display Chat History only when in Chat/Search modes
        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])

        # The Input Loop
        if prompt := st.chat_input("Ask a question about the CUNY network..."):

            # 1. LOG THE SEARCH TO THE DATABASE
            log_search(profile['user_id'], prompt)

            # Show User Message
            st.session_state.messages.append({"role": "user", "content": prompt})
            with st.chat_message("user"):
                st.markdown(prompt)

            with st.spinner("Analyzing network signals..."):
                matches, filters = search_civic_network(prompt, df)

                if mode == "🔍 Partner Search":
                    if not matches.empty:
                        response = f"✅ **Found {len(matches)} Partners!**\n\n"
                        for _, row in matches.iterrows():
                            response += f"--- \n👤 **{row['Contact Name']}** — *{row['Campus']}*\n"
                            response += f"**Role:** {row['Role/Title']}\n"
                            response += f"**Focus:** {row['Civic Domains']} | {row['Communities Served']}\n"
                    else:
                        response = "❌ No direct matches found. Try broadening your terms."


                elif mode == "💬 Civic Chat":

                    if not matches.empty:

                        insight = generate_civic_insight(prompt, matches)

                        response = f"**Civic Insight:**\n\n{insight}\n\n*(Analysis based on {len(matches)} relevant entries)*"

                    else:

                        response = "I couldn't find enough relevant data to answer that specifically."

                    # ---------------------------------------------------------

                    # MODE 4: NETWORK ANALYSIS (The "Deep Dive")

                    # ---------------------------------------------------------

                elif mode == "🧠 Network Analysis":

                    st.info("Reading the entire CUNY database. This deep analysis may take 10-15 seconds...")

                    # We bypass the 'matches' filter entirely and pass 'df' (the whole database)

                    insight = generate_civic_insight(prompt, df)

                    response = f"**Deep Network Insight:**\n\n{insight}\n\n*(Analysis based on all {len(df)} network entries)*"

                st.session_state.history.append(prompt)

            # Show Assistant Message
            st.session_state.messages.append({"role": "assistant", "content": response})
            with st.chat_message("assistant"):
                st.markdown(response)
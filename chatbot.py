from sklearn.feature_extraction.text import CountVectorizer
from sklearn.svm import SVC
from sklearn.pipeline import make_pipeline
from models import get_db_connection

training_data = [
    # Greetings
    ("hello", "greeting"),
    ("hi there", "greeting"),
    ("good morning", "greeting"),
    ("good evening", "greeting"),
    ("hey campus connect", "greeting"),
    ("hi", "greeting"),
    ("hey", "greeting"),
    ("hello there", "greeting"),
    ("hi campusconnect", "greeting"),
    ("hello campusconnect bot", "greeting"),

    # Events and browsing
    ("what events are coming up?", "event_inquiry"),
    ("what workshops are available this month?", "event_inquiry"),
    ("is there any upcoming event?", "event_inquiry"),
    ("is there any workshop?", "event_inquiry"),
    ("what's happening next week?", "event_inquiry"),
    ("can you tell me about upcoming events?", "event_inquiry"),
    ("what events are scheduled?", "event_inquiry"),
    ("show me campus connect events", "event_inquiry"),
    ("where can i see hackathons and competitions?", "event_inquiry"),
    ("list upcoming events", "event_inquiry"),
    ("show upcoming events", "event_inquiry"),
    ("any events today?", "event_inquiry"),
    ("events this week", "event_inquiry"),
    ("what events are there on campus?", "event_inquiry"),
    ("what hackathons are available?", "event_inquiry"),
    ("what seminars are planned?", "event_inquiry"),

    # Registrations
    ("how do i register for the workshop?", "registration_help"),
    ("how to sign up for the seminar?", "registration_help"),
    ("register for the hackathon", "registration_help"),
    ("how do i register for an event in campusconnect", "registration_help"),
    ("how do i unregister from an event", "registration_help"),
    ("how can i register for an event?", "registration_help"),
    ("steps to register for an event", "registration_help"),
    ("i want to sign up for an event", "registration_help"),
    ("cancel my event registration", "registration_help"),
    ("remove me from a registered event", "registration_help"),
    ("how to withdraw from an event", "registration_help"),

    # Teams
    ("how do i create a team?", "team_help"),
    ("how can i join a team?", "team_help"),
    ("how do team invitations work?", "team_help"),
    ("where is the team dashboard?", "team_help"),
    ("create a team for an event", "team_help"),
    ("how to form a team", "team_help"),
    ("invite friends to my team", "team_help"),
    ("join an existing team", "team_help"),
    ("how do team requests work?", "team_help"),
    ("where can i manage my team?", "team_help"),

    # Abstracts
    ("how do i submit an abstract?", "abstract_help"),
    ("where do i upload my abstract?", "abstract_help"),
    ("how can i edit my abstract?", "abstract_help"),
    ("does this event require an abstract?", "abstract_help"),
    ("steps to submit my abstract", "abstract_help"),
    ("how to upload abstract file", "abstract_help"),
    ("can i edit my abstract after submitting?", "abstract_help"),
    ("where is the abstract submission page?", "abstract_help"),
    ("do i need to submit an abstract for this event?", "abstract_help"),
    ("what is the abstract deadline?", "abstract_help"),

    # Plagiarism and checker
    ("what is plagiarism?", "plagiarism_info"),
    ("how does the plagiarism checker work?", "plagiarism_info"),
    ("why was my abstract flagged for plagiarism?", "plagiarism_info"),
    ("what is the plagiarism threshold?", "plagiarism_info"),
    ("check my abstract for plagiarism", "plagiarism_info"),
    ("plagiarism check for my abstract", "plagiarism_info"),
    ("my plagiarism score is high", "plagiarism_info"),
    ("what does similarity score mean?", "plagiarism_info"),
    ("how can i reduce plagiarism in my abstract?", "plagiarism_info"),
    ("plagarism checker details", "plagiarism_info"),

    # Dashboard and general usage
    ("how do i check my dashboard?", "dashboard_help"),
    ("where do i see my registered events?", "dashboard_help"),
    ("how do i view my abstract submissions?", "dashboard_help"),
    ("what can i do with campusconnect?", "general_cc"),
    ("what is campusconnect?", "general_cc"),
    ("how does this portal help students?", "general_cc"),
    ("open my campusconnect dashboard", "dashboard_help"),
    ("where can i see my upcoming events?", "dashboard_help"),
    ("where can i see my teams?", "dashboard_help"),
    ("what can i do on this portal?", "general_cc"),
    ("explain campusconnect features", "general_cc"),
    ("how is campusconnect useful?", "general_cc"),

    # Contact/support
    ("who should I contact for help?", "contact_info"),
    ("how do I reach the support team?", "contact_info"),
    ("get me the number for support", "contact_info"),
    ("how can i contact the admin of campusconnect?", "contact_info"),
    ("need help with campusconnect", "contact_info"),
    ("who can i contact for support?", "contact_info"),
    ("how do i get technical support?", "contact_info"),
    ("where can i report a problem?", "contact_info"),
]

phrases = [d[0] for d in training_data]
intents = [d[1] for d in training_data]

model = make_pipeline(CountVectorizer(), SVC())
model.fit(phrases, intents)


def _get_upcoming_events(limit=5):
    """Fetch a small list of upcoming/ongoing events from the database."""
    conn = get_db_connection()
    try:
        rows = conn.execute(
            """
            SELECT title, event_type, start_date, venue, status
            FROM events
            WHERE status IN ('upcoming', 'ongoing')
            ORDER BY start_date ASC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return rows
    except Exception:
        return []
    finally:
        conn.close()


def get_response(user_query):
    predicted_intent = model.predict([user_query])[0]
    
    if predicted_intent == "event_inquiry":
        events = _get_upcoming_events()
        if not events:
            return (
                "I couldn't find any upcoming CampusConnect events right now. "
                "No events with status 'upcoming' or 'ongoing' are currently stored in the database."
            )
        descriptions = []
        for e in events:
            event_type = (e["event_type"] or "").replace("_", " ").title()
            start = e["start_date"]
            venue = e["venue"] or "TBA"
            descriptions.append(
                f"{e['title']} ({event_type}) on {start} at {venue}"
            )
        return (
            "Upcoming CampusConnect events in the database: "
            + "; ".join(descriptions)
            + "."
        )
    elif predicted_intent == "registration_help":
        return (
            "To register for a CampusConnect event, go to the Events page, open the event "
            "you are interested in, and click the Register button. For team events, you may need "
            "to create or join a team first from the Teams section or team dashboard."
        )
    elif predicted_intent == "team_help":
        return (
            "Teams in CampusConnect are created per event. From an event that supports teams, "
            "you can create a new team or invite members from the team dashboard. Other students "
            "can discover public teams and send join requests through the team recruitment pages."
        )
    elif predicted_intent == "abstract_help":
        return (
            "Abstracts are managed per event in CampusConnect. After you register for an event "
            "that requires an abstract, the event details page will show a Submit Abstract button. "
            "You can upload your file, edit the text, and finalize it before the abstract deadline."
        )
    elif predicted_intent == "plagiarism_info":
        return (
            "CampusConnect uses a built-in plagiarism checker for abstracts. It compares your text "
            "against other submissions for the same event and shows a similarity percentage. "
            "If the score is above the event's threshold, your abstract may be flagged and you might "
            "need to revise it before final submission."
        )
    elif predicted_intent == "dashboard_help":
        return (
            "Your CampusConnect dashboard shows a summary of your activity: registered events, "
            "teams, abstract submissions, and notifications. Use it to quickly continue where you "
            "left off or open specific event details."
        )
    elif predicted_intent == "general_cc":
        return (
            "CampusConnect is a portal for managing campus events, teams, and abstracts. "
            "Students can discover events, register, form teams, submit abstracts, and track "
            "plagiarism scores. Event managers can configure requirements, review submissions, "
            "and manage participants from their dashboards."
        )
    elif predicted_intent == "greeting":
        return (
            "Hello! I am your CampusConnect assistant. You can ask me about events, "
            "registrations, teams, abstracts, and plagiarism checks in this project."
        )
    elif predicted_intent == "contact_info":
        return (
            "If you need extra help, open the Contact or Help page inside CampusConnect to see "
            "official support information, or reach out to your campus coordinator."
        )
    else:
        return (
            "I'm not sure about that yet. Try asking me about CampusConnect events, "
            "registrations, teams, abstracts, or the plagiarism checker."
        )
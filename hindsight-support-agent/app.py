import os
import re
import uuid
import sqlite3
import calendar
import shutil

from datetime import datetime, date
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv
from openai import OpenAI


# ============================================================
# CONFIGURATION
# ============================================================

load_dotenv()

APP_TITLE = "TechNova Customer Support Agent"

DB_FILE = "technova_customers.db"

UPLOAD_DIR = Path("customer_uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

GROQ_API_KEY = "mmmm"  //replace with your API KEY HERE

GROQ_MODEL = os.getenv(
    "GROQ_MODEL",
    "openai/gpt-oss-20b"
)

if GROQ_API_KEY:
    groq_client = OpenAI(
        api_key="MMMM", //replace with your API KEY HERE
        base_url="https://api.groq.com/openai/v1"
    )
else:
    groq_client = None


# ============================================================
# PAGE CONFIG
# ============================================================

st.set_page_config(
    page_title=APP_TITLE,
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ============================================================
# DATABASE
# ============================================================

@st.cache_resource
def get_database():

    conn = sqlite3.connect(
        DB_FILE,
        check_same_thread=False
    )

    conn.row_factory = sqlite3.Row

    return conn


db = get_database()


# ============================================================
# UTILITY
# ============================================================

def now_iso():
    return datetime.now().isoformat(
        timespec="seconds"
    )


def new_customer_id():
    return "cust_" + uuid.uuid4().hex[:12]


def new_conversation_id():
    return "conv_" + uuid.uuid4().hex[:12]


# ============================================================
# DATABASE INITIALIZATION
# ============================================================

def column_exists(table_name, column_name):

    rows = db.execute(
        f"PRAGMA table_info({table_name})"
    ).fetchall()

    return any(
        row[1] == column_name
        for row in rows
    )


def add_column_if_missing(
    table_name,
    column_name,
    definition
):

    if not column_exists(
        table_name,
        column_name
    ):

        db.execute(
            f"""
            ALTER TABLE {table_name}
            ADD COLUMN {column_name} {definition}
            """
        )


def initialize_database():

    # --------------------------------------------------------
    # CUSTOMERS
    # --------------------------------------------------------

    db.execute(
        """
        CREATE TABLE IF NOT EXISTS customers (
            customer_id TEXT PRIMARY KEY,
            first_name TEXT NOT NULL,
            last_name TEXT NOT NULL,
            mobile TEXT NOT NULL,
            dob TEXT NOT NULL,
            country TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )

    # --------------------------------------------------------
    # CONVERSATIONS
    # --------------------------------------------------------

    db.execute(
        """
        CREATE TABLE IF NOT EXISTS conversations (
            conversation_id TEXT PRIMARY KEY,
            customer_id TEXT NOT NULL,
            title TEXT DEFAULT 'New Chat',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )

    # --------------------------------------------------------
    # MESSAGES
    # --------------------------------------------------------

    db.execute(
        """
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id TEXT,
            customer_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )

    # --------------------------------------------------------
    # MIGRATE OLD DATABASE
    # --------------------------------------------------------

    add_column_if_missing(
        "messages",
        "conversation_id",
        "TEXT"
    )

    # --------------------------------------------------------
    # PRIVATE CUSTOMER MEMORY
    # --------------------------------------------------------

    db.execute(
        """
        CREATE TABLE IF NOT EXISTS customer_memory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id TEXT NOT NULL,
            memory_key TEXT NOT NULL,
            memory_value TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,

            UNIQUE(
                customer_id,
                memory_key
            )
        )
        """
    )

    # --------------------------------------------------------
    # ATTACHMENTS
    # --------------------------------------------------------

    db.execute(
        """
        CREATE TABLE IF NOT EXISTS attachments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            message_id INTEGER,
            customer_id TEXT NOT NULL,
            conversation_id TEXT NOT NULL,
            original_name TEXT NOT NULL,
            stored_path TEXT NOT NULL,
            mime_type TEXT,
            created_at TEXT NOT NULL
        )
        """
    )

    db.commit()

    # --------------------------------------------------------
    # MIGRATE OLD MESSAGES INTO CONVERSATION
    # --------------------------------------------------------

    old_customers = db.execute(
        """
        SELECT DISTINCT customer_id
        FROM messages
        WHERE conversation_id IS NULL
        """
    ).fetchall()

    for row in old_customers:

        customer_id = row["customer_id"]

        existing_conversation = db.execute(
            """
            SELECT conversation_id
            FROM conversations
            WHERE customer_id = ?
            ORDER BY created_at ASC
            LIMIT 1
            """,
            (customer_id,)
        ).fetchone()

        if existing_conversation:

            conversation_id = (
                existing_conversation["conversation_id"]
            )

        else:

            conversation_id = new_conversation_id()

            db.execute(
                """
                INSERT INTO conversations (
                    conversation_id,
                    customer_id,
                    title,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    conversation_id,
                    customer_id,
                    "Previous Chat",
                    now_iso(),
                    now_iso()
                )
            )

        db.execute(
            """
            UPDATE messages
            SET conversation_id = ?
            WHERE customer_id = ?
              AND conversation_id IS NULL
            """,
            (
                conversation_id,
                customer_id
            )
        )

    db.commit()


initialize_database()


# ============================================================
# COUNTRY DATA
# ============================================================

COUNTRY_DATA = [
    ("Afghanistan", "+93"),
    ("Albania", "+355"),
    ("Algeria", "+213"),
    ("Andorra", "+376"),
    ("Angola", "+244"),
    ("Antigua and Barbuda", "+1"),
    ("Argentina", "+54"),
    ("Armenia", "+374"),
    ("Australia", "+61"),
    ("Austria", "+43"),
    ("Azerbaijan", "+994"),
    ("Bahamas", "+1"),
    ("Bahrain", "+973"),
    ("Bangladesh", "+880"),
    ("Barbados", "+1"),
    ("Belarus", "+375"),
    ("Belgium", "+32"),
    ("Belize", "+501"),
    ("Benin", "+229"),
    ("Bhutan", "+975"),
    ("Bolivia", "+591"),
    ("Bosnia and Herzegovina", "+387"),
    ("Botswana", "+267"),
    ("Brazil", "+55"),
    ("Brunei", "+673"),
    ("Bulgaria", "+359"),
    ("Burkina Faso", "+226"),
    ("Burundi", "+257"),
    ("Cambodia", "+855"),
    ("Cameroon", "+237"),
    ("Canada", "+1"),
    ("Cape Verde", "+238"),
    ("Central African Republic", "+236"),
    ("Chad", "+235"),
    ("Chile", "+56"),
    ("China", "+86"),
    ("Colombia", "+57"),
    ("Comoros", "+269"),
    ("Congo", "+242"),
    ("Costa Rica", "+506"),
    ("Croatia", "+385"),
    ("Cuba", "+53"),
    ("Cyprus", "+357"),
    ("Czech Republic", "+420"),
    ("Denmark", "+45"),
    ("Djibouti", "+253"),
    ("Dominica", "+1"),
    ("Dominican Republic", "+1"),
    ("Ecuador", "+593"),
    ("Egypt", "+20"),
    ("El Salvador", "+503"),
    ("Equatorial Guinea", "+240"),
    ("Eritrea", "+291"),
    ("Estonia", "+372"),
    ("Eswatini", "+268"),
    ("Ethiopia", "+251"),
    ("Fiji", "+679"),
    ("Finland", "+358"),
    ("France", "+33"),
    ("Gabon", "+241"),
    ("Gambia", "+220"),
    ("Georgia", "+995"),
    ("Germany", "+49"),
    ("Ghana", "+233"),
    ("Greece", "+30"),
    ("Grenada", "+1"),
    ("Guatemala", "+502"),
    ("Guinea", "+224"),
    ("Guinea-Bissau", "+245"),
    ("Guyana", "+592"),
    ("Haiti", "+509"),
    ("Honduras", "+504"),
    ("Hungary", "+36"),
    ("Iceland", "+354"),
    ("India", "+91"),
    ("Indonesia", "+62"),
    ("Iran", "+98"),
    ("Iraq", "+964"),
    ("Ireland", "+353"),
    ("Israel", "+972"),
    ("Italy", "+39"),
    ("Jamaica", "+1"),
    ("Japan", "+81"),
    ("Jordan", "+962"),
    ("Kazakhstan", "+7"),
    ("Kenya", "+254"),
    ("Kiribati", "+686"),
    ("Kuwait", "+965"),
    ("Kyrgyzstan", "+996"),
    ("Laos", "+856"),
    ("Latvia", "+371"),
    ("Lebanon", "+961"),
    ("Lesotho", "+266"),
    ("Liberia", "+231"),
    ("Libya", "+218"),
    ("Liechtenstein", "+423"),
    ("Lithuania", "+370"),
    ("Luxembourg", "+352"),
    ("Madagascar", "+261"),
    ("Malawi", "+265"),
    ("Malaysia", "+60"),
    ("Maldives", "+960"),
    ("Mali", "+223"),
    ("Malta", "+356"),
    ("Marshall Islands", "+692"),
    ("Mauritania", "+222"),
    ("Mauritius", "+230"),
    ("Mexico", "+52"),
    ("Micronesia", "+691"),
    ("Moldova", "+373"),
    ("Monaco", "+377"),
    ("Mongolia", "+976"),
    ("Montenegro", "+382"),
    ("Morocco", "+212"),
    ("Mozambique", "+258"),
    ("Myanmar", "+95"),
    ("Namibia", "+264"),
    ("Nauru", "+674"),
    ("Nepal", "+977"),
    ("Netherlands", "+31"),
    ("New Zealand", "+64"),
    ("Nicaragua", "+505"),
    ("Niger", "+227"),
    ("Nigeria", "+234"),
    ("North Korea", "+850"),
    ("North Macedonia", "+389"),
    ("Norway", "+47"),
    ("Oman", "+968"),
    ("Pakistan", "+92"),
    ("Palau", "+680"),
    ("Palestine", "+970"),
    ("Panama", "+507"),
    ("Papua New Guinea", "+675"),
    ("Paraguay", "+595"),
    ("Peru", "+51"),
    ("Philippines", "+63"),
    ("Poland", "+48"),
    ("Portugal", "+351"),
    ("Qatar", "+974"),
    ("Romania", "+40"),
    ("Russia", "+7"),
    ("Rwanda", "+250"),
    ("Saint Kitts and Nevis", "+1"),
    ("Saint Lucia", "+1"),
    ("Saint Vincent and the Grenadines", "+1"),
    ("Samoa", "+685"),
    ("San Marino", "+378"),
    ("Sao Tome and Principe", "+239"),
    ("Saudi Arabia", "+966"),
    ("Senegal", "+221"),
    ("Serbia", "+381"),
    ("Seychelles", "+248"),
    ("Sierra Leone", "+232"),
    ("Singapore", "+65"),
    ("Slovakia", "+421"),
    ("Slovenia", "+386"),
    ("Solomon Islands", "+677"),
    ("Somalia", "+252"),
    ("South Africa", "+27"),
    ("South Korea", "+82"),
    ("South Sudan", "+211"),
    ("Spain", "+34"),
    ("Sri Lanka", "+94"),
    ("Sudan", "+249"),
    ("Suriname", "+597"),
    ("Sweden", "+46"),
    ("Switzerland", "+41"),
    ("Syria", "+963"),
    ("Taiwan", "+886"),
    ("Tajikistan", "+992"),
    ("Tanzania", "+255"),
    ("Thailand", "+66"),
    ("Timor-Leste", "+670"),
    ("Togo", "+228"),
    ("Tonga", "+676"),
    ("Trinidad and Tobago", "+1"),
    ("Tunisia", "+216"),
    ("Turkey", "+90"),
    ("Turkmenistan", "+993"),
    ("Tuvalu", "+688"),
    ("Uganda", "+256"),
    ("Ukraine", "+380"),
    ("United Arab Emirates", "+971"),
    ("United Kingdom", "+44"),
    ("United States", "+1"),
    ("Uruguay", "+598"),
    ("Uzbekistan", "+998"),
    ("Vanuatu", "+678"),
    ("Vatican City", "+379"),
    ("Venezuela", "+58"),
    ("Vietnam", "+84"),
    ("Yemen", "+967"),
    ("Zambia", "+260"),
    ("Zimbabwe", "+263"),
]

COUNTRY_NAMES = [
    country[0]
    for country in COUNTRY_DATA
]

COUNTRY_CODES = {
    country: code
    for country, code in COUNTRY_DATA
}


# ============================================================
# CUSTOMER FUNCTIONS
# ============================================================

def get_customers():

    return db.execute(
        """
        SELECT *
        FROM customers
        ORDER BY first_name COLLATE NOCASE,
                 last_name COLLATE NOCASE
        """
    ).fetchall()


def get_customer(customer_id):

    return db.execute(
        """
        SELECT *
        FROM customers
        WHERE customer_id = ?
        """,
        (customer_id,)
    ).fetchone()


def create_customer(
    first_name,
    last_name,
    mobile,
    dob,
    country
):

    customer_id = new_customer_id()

    db.execute(
        """
        INSERT INTO customers (
            customer_id,
            first_name,
            last_name,
            mobile,
            dob,
            country,
            created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            customer_id,
            first_name.strip(),
            last_name.strip(),
            mobile.strip(),
            dob,
            country,
            now_iso()
        )
    )

    db.commit()

    return customer_id


# ============================================================
# PERMANENT CUSTOMER DELETION
# ============================================================

def permanently_delete_customer(customer_id):
    """
    Permanently removes all data belonging to one customer.

    Deletes:
        - customer profile
        - conversations
        - messages
        - private customer memory
        - attachment database records
        - uploaded files from disk

    There is intentionally no restore/undo mechanism.
    """

    # --------------------------------------------------------
    # Find uploaded files before deleting DB records
    # --------------------------------------------------------

    attachments = db.execute(
        """
        SELECT stored_path
        FROM attachments
        WHERE customer_id = ?
        """,
        (customer_id,)
    ).fetchall()

    # --------------------------------------------------------
    # Delete individual attachment files
    # --------------------------------------------------------

    for attachment in attachments:

        file_path = Path(
            attachment["stored_path"]
        )

        try:

            if file_path.exists():

                file_path.unlink()

        except Exception:

            pass

    # --------------------------------------------------------
    # Delete customer's complete upload directory
    # --------------------------------------------------------

    customer_upload_folder = (
        UPLOAD_DIR / customer_id
    )

    try:

        if customer_upload_folder.exists():

            shutil.rmtree(
                customer_upload_folder
            )

    except Exception:

        pass

    # --------------------------------------------------------
    # Delete attachment records
    # --------------------------------------------------------

    db.execute(
        """
        DELETE FROM attachments
        WHERE customer_id = ?
        """,
        (customer_id,)
    )

    # --------------------------------------------------------
    # Delete messages
    # --------------------------------------------------------

    db.execute(
        """
        DELETE FROM messages
        WHERE customer_id = ?
        """,
        (customer_id,)
    )

    # --------------------------------------------------------
    # Delete private memory
    # --------------------------------------------------------

    db.execute(
        """
        DELETE FROM customer_memory
        WHERE customer_id = ?
        """,
        (customer_id,)
    )

    # --------------------------------------------------------
    # Delete conversations
    # --------------------------------------------------------

    db.execute(
        """
        DELETE FROM conversations
        WHERE customer_id = ?
        """,
        (customer_id,)
    )

    # --------------------------------------------------------
    # Delete customer
    # --------------------------------------------------------

    db.execute(
        """
        DELETE FROM customers
        WHERE customer_id = ?
        """,
        (customer_id,)
    )

    db.commit()


# ============================================================
# CONVERSATION FUNCTIONS
# ============================================================

def create_conversation(
    customer_id,
    title="New Chat"
):

    conversation_id = new_conversation_id()

    db.execute(
        """
        INSERT INTO conversations (
            conversation_id,
            customer_id,
            title,
            created_at,
            updated_at
        )
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            conversation_id,
            customer_id,
            title,
            now_iso(),
            now_iso()
        )
    )

    db.commit()

    return conversation_id


def get_conversations(
    customer_id,
    limit=None
):

    if limit:

        return db.execute(
            """
            SELECT *
            FROM conversations
            WHERE customer_id = ?
            ORDER BY updated_at DESC
            LIMIT ?
            """,
            (
                customer_id,
                limit
            )
        ).fetchall()

    return db.execute(
        """
        SELECT *
        FROM conversations
        WHERE customer_id = ?
        ORDER BY updated_at DESC
        """,
        (customer_id,)
    ).fetchall()


def get_conversation(
    conversation_id,
    customer_id
):

    return db.execute(
        """
        SELECT *
        FROM conversations
        WHERE conversation_id = ?
          AND customer_id = ?
        """,
        (
            conversation_id,
            customer_id
        )
    ).fetchone()


def update_conversation_title(
    conversation_id,
    customer_id,
    title
):

    db.execute(
        """
        UPDATE conversations
        SET title = ?,
            updated_at = ?
        WHERE conversation_id = ?
          AND customer_id = ?
        """,
        (
            title[:60],
            now_iso(),
            conversation_id,
            customer_id
        )
    )

    db.commit()


def cleanup_empty_chats(customer_id):

    empty_chats = db.execute(
        """
        SELECT c.conversation_id
        FROM conversations c
        WHERE c.customer_id = ?
          AND NOT EXISTS (
              SELECT 1
              FROM messages m
              WHERE m.conversation_id =
                    c.conversation_id
          )
        ORDER BY c.updated_at DESC
        """,
        (customer_id,)
    ).fetchall()

    if len(empty_chats) <= 1:

        return

    for chat in empty_chats[1:]:

        db.execute(
            """
            DELETE FROM conversations
            WHERE conversation_id = ?
              AND customer_id = ?
            """,
            (
                chat["conversation_id"],
                customer_id
            )
        )

    db.commit()


# ============================================================
# MESSAGE FUNCTIONS
# ============================================================

def save_message(
    customer_id,
    conversation_id,
    role,
    content
):

    cursor = db.execute(
        """
        INSERT INTO messages (
            conversation_id,
            customer_id,
            role,
            content,
            created_at
        )
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            conversation_id,
            customer_id,
            role,
            content,
            now_iso()
        )
    )

    db.execute(
        """
        UPDATE conversations
        SET updated_at = ?
        WHERE conversation_id = ?
          AND customer_id = ?
        """,
        (
            now_iso(),
            conversation_id,
            customer_id
        )
    )

    db.commit()

    return cursor.lastrowid


def get_messages(
    customer_id,
    conversation_id
):

    return db.execute(
        """
        SELECT *
        FROM messages
        WHERE customer_id = ?
          AND conversation_id = ?
        ORDER BY id ASC
        """,
        (
            customer_id,
            conversation_id
        )
    ).fetchall()


# ============================================================
# PRIVATE CUSTOMER MEMORY
# ============================================================

NOT_FOUND_MESSAGE = (
    "I haven't found that information in my database yet. "
    "Could you please update it?"
)


def save_customer_memory(
    customer_id,
    memory_key,
    memory_value
):

    db.execute(
        """
        INSERT INTO customer_memory (
            customer_id,
            memory_key,
            memory_value,
            created_at,
            updated_at
        )
        VALUES (?, ?, ?, ?, ?)

        ON CONFLICT(
            customer_id,
            memory_key
        )
        DO UPDATE SET
            memory_value = excluded.memory_value,
            updated_at = excluded.updated_at
        """,
        (
            customer_id,
            memory_key,
            memory_value,
            now_iso(),
            now_iso()
        )
    )

    db.commit()


def get_customer_memory(
    customer_id,
    memory_key
):

    row = db.execute(
        """
        SELECT memory_value
        FROM customer_memory
        WHERE customer_id = ?
          AND memory_key = ?
        """,
        (
            customer_id,
            memory_key
        )
    ).fetchone()

    if row:

        return row["memory_value"]

    return None


# ============================================================
# CUSTOMER UPDATE EXTRACTION
# ============================================================

def extract_customer_update(text):

    patterns = [

        (
            r"\bmy\s+favorite\s+movie\s+is\s+(.+)",
            "favorite_movie"
        ),

        (
            r"\bmy\s+favourite\s+movie\s+is\s+(.+)",
            "favorite_movie"
        ),

        (
            r"\bmy\s+favorite\s+color\s+is\s+(.+)",
            "favorite_color"
        ),

        (
            r"\bmy\s+favourite\s+colour\s+is\s+(.+)",
            "favorite_color"
        ),

        (
            r"\bmy\s+favorite\s+food\s+is\s+(.+)",
            "favorite_food"
        ),

        (
            r"\bmy\s+favorite\s+sport\s+is\s+(.+)",
            "favorite_sport"
        ),

        (
            r"\bmy\s+father'?s\s+name\s+is\s+(.+)",
            "father_name"
        ),

        (
            r"\bmy\s+mother'?s\s+name\s+is\s+(.+)",
            "mother_name"
        ),

        (
            r"\bmy\s+bank\s+name\s+is\s+(.+)",
            "bank_name"
        ),

        (
            r"\bmy\s+account\s+number\s+is\s+([0-9]+)",
            "account_number"
        ),

        (
            r"\bmy\s+account\s+no\.?\s+is\s+([0-9]+)",
            "account_number"
        ),

        (
            r"\bmy\s+customer\s+number\s+is\s+([A-Za-z0-9_-]+)",
            "customer_number"
        ),

        (
            r"\bmy\s+email\s+is\s+([^\s]+@[^\s]+)",
            "email"
        ),

        (
            r"\bmy\s+address\s+is\s+(.+)",
            "address"
        ),

        (
            r"\bmy\s+city\s+is\s+(.+)",
            "city"
        ),

        (
            r"\bmy\s+profession\s+is\s+(.+)",
            "profession"
        ),

        (
            r"\bmy\s+job\s+is\s+(.+)",
            "profession"
        ),

        (
            r"\bmy\s+employer\s+is\s+(.+)",
            "employer"
        ),

        (
            r"\bmy\s+pan\s+number\s+is\s+([A-Za-z0-9]+)",
            "pan_number"
        ),

        (
            r"\bmy\s+aadhaar\s+number\s+is\s+([0-9]+)",
            "aadhaar_number"
        ),

        (
            r"\bmy\s+aadhar\s+number\s+is\s+([0-9]+)",
            "aadhaar_number"
        ),

        (
            r"\bi\s+deposited\s+(?:an?\s+)?(?:amount\s+)?(?:of\s+)?([0-9,]+)",
            "last_deposit_amount"
        ),
    ]

    for pattern, key in patterns:

        match = re.search(
            pattern,
            text,
            re.IGNORECASE
        )

        if match:

            value = match.group(1).strip()

            value = value.rstrip(
                ".,!?"
            )

            return key, value

    return None, None


# ============================================================
# CUSTOMER QUESTION DETECTION
# ============================================================

# ============================================================
# PRIVATE DATA SHARING / DISCLOSURE DETECTION
# ============================================================

PRIVATE_DATA_SHARING_RESPONSE = (
    "I can't share or disclose your private customer information "
    "with an external AI service or third party. Your sensitive "
    "customer data remains inside the application's private "
    "customer record."
)


def is_private_data_sharing_request(text):
    """
    Detect requests that ask the application to expose private
    customer information to an LLM, AI service, third party, or
    another person/service. This check must run BEFORE the normal
    customer-data lookup so the private value is never returned.
    """

    q = text.lower().strip()

    sensitive_fields = [
        "name",
        "first name",
        "last name",
        "phone number",
        "mobile number",
        "phone",
        "mobile",
        "account number",
        "account no",
        "customer number",
        "address",
        "email",
        "date of birth",
        "dob",
        "pan",
        "aadhaar",
        "aadhar",
        "bank account",
        "account balance",
        "deposit",
    ]

    # These verbs indicate transfer/disclosure rather than simply
    # asking the selected customer for their own information.
    # Do NOT include generic verbs such as "tell", "give", or
    # "provide" here because valid questions include:
    #   "tell me my phone number"
    #   "give me my DOB"
    sharing_words = [
        "share",
        "sharing",
        "shared",
        "send",
        "sending",
        "sent",
        "reveal",
        "revealing",
        "expose",
        "exposing",
        "forward",
        "forwarding",
        "transmit",
        "transmitting",
        "disclose",
        "disclosing",
        "publish",
        "publishing",
        "upload",
        "uploading",
        "pass",
        "passing",
    ]

    external_targets = [
        "llm",
        "ai",
        "chatgpt",
        "groq",
        "openai",
        "external service",
        "external system",
        "third party",
        "third-party",
        "another service",
        "another ai",
        "another model",
    ]

    has_sensitive_field = any(
        field in q
        for field in sensitive_fields
    )

    has_sharing_word = any(
        word in q
        for word in sharing_words
    )

    has_external_target = any(
        target in q
        for target in external_targets
    )

    # Statements indicating that private data is already being shared
    # must never fall through to the local customer lookup.
    already_disclosing = any(
        re.search(pattern, q)
        for pattern in [
            r"\byou\s+are\s+sharing\b",
            r"\byou're\s+sharing\b",
            r"\byou\s+have\s+shared\b",
            r"\byou\s+shared\b",
            r"\byou\s+sent\b",
            r"\byou\s+revealed\b",
            r"\byou\s+disclosed\b",
        ]
    )

    if has_sensitive_field and already_disclosing:
        return True

    # Explicit request to share private data externally.
    if (
        has_sensitive_field
        and has_sharing_word
        and has_external_target
    ):
        return True

    # Also protect direct requests to share private data, even when
    # the destination is not explicitly mentioned.
    if (
        has_sensitive_field
        and has_sharing_word
    ):
        return True

    return False


# ============================================================
# CUSTOMER QUESTION DETECTION
# ============================================================

def normalize_short_question(text):
    """Normalize punctuation/spacing for short customer-data questions."""
    q = (text or "").lower().strip()
    q = re.sub(r"[?!.]+", " ", q)
    q = re.sub(r"\s+", " ", q).strip()
    return q


def short_customer_field_from_question(text):
    """
    Recognize short customer-data questions when a customer is already
    selected. Examples:

        name?
        phone number?
        phone?
        mobile?
        dob?
        address?
        email?
        acct no?
        fav movie?

    This function is intentionally limited to short/field-style questions.
    It does NOT make general sentences such as "what is a phone number?"
    private-data questions.
    """

    q = normalize_short_question(text)

    # Remove common request prefixes/suffixes. These are safe here because
    # the privacy-sharing detector runs BEFORE customer lookup. Therefore:
    #   "give me my phone number" -> local selected-customer lookup
    #   "give my phone number to ChatGPT" -> privacy block first
    q = re.sub(
        r"^(?:what\s+is|what'?s|whats|tell\s+me|give\s+me|show\s+me|show|tell)\s+",
        "",
        q
    )
    q = re.sub(r"\b(please|pls|plz)\b", " ", q)
    q = re.sub(r"\s+", " ", q).strip()

    aliases = {
        # Direct customer record
        "name": "name",
        "my name": "name",
        "full name": "name",
        "fname": "first_name",
        "first name": "first_name",
        "my first name": "first_name",
        "first": "first_name",
        "lname": "last_name",
        "last name": "last_name",
        "my last name": "last_name",
        "last": "last_name",
        "surname": "last_name",

        "phone": "mobile",
        "phone number": "mobile",
        "my phone": "mobile",
        "my phone number": "mobile",
        "mobile": "mobile",
        "mobile number": "mobile",
        "my mobile": "mobile",
        "my mobile number": "mobile",
        "mob": "mobile",
        "mob no": "mobile",
        "mobile no": "mobile",
        "phone no": "mobile",
        "contact": "mobile",
        "contact number": "mobile",
        "contact no": "mobile",

        "dob": "dob",
        "d.o.b": "dob",
        "date of birth": "dob",
        "birth date": "dob",
        "birthday": "dob",
        "birthdate": "dob",
        "my dob": "dob",
        "my date of birth": "dob",

        "country": "country",
        "my country": "country",

        # Customer/account identifiers stored in private memory
        "account": "account_number",
        "account number": "account_number",
        "account no": "account_number",
        "acct": "account_number",
        "acct no": "account_number",
        "acct number": "account_number",
        "customer number": "customer_number",
        "customer no": "customer_number",
        "cust no": "customer_number",
        "cust number": "customer_number",
        "customer id": "customer_number",
        "cust id": "customer_number",

        # Private memory
        "favorite movie": "favorite_movie",
        "favourite movie": "favorite_movie",
        "fav movie": "favorite_movie",
        "movie": "favorite_movie",
        "film": "favorite_movie",
        "fav film": "favorite_movie",

        "favorite color": "favorite_color",
        "favourite color": "favorite_color",
        "favorite colour": "favorite_color",
        "favourite colour": "favorite_color",
        "fav color": "favorite_color",
        "fav colour": "favorite_color",
        "color": "favorite_color",
        "colour": "favorite_color",

        "favorite food": "favorite_food",
        "favourite food": "favorite_food",
        "fav food": "favorite_food",
        "food": "favorite_food",

        "favorite sport": "favorite_sport",
        "favourite sport": "favorite_sport",
        "fav sport": "favorite_sport",
        "sport": "favorite_sport",

        "father": "father_name",
        "dad": "father_name",
        "father name": "father_name",
        "dad name": "father_name",

        "mother": "mother_name",
        "mom": "mother_name",
        "mum": "mother_name",
        "mother name": "mother_name",
        "mom name": "mother_name",
        "mum name": "mother_name",

        "bank": "bank_name",
        "bank name": "bank_name",
        "my bank": "bank_name",

        "address": "address",
        "my address": "address",

        "email": "email",
        "email address": "email",
        "mail": "email",
        "my email": "email",

        "profession": "profession",
        "job": "profession",
        "occupation": "profession",
        "my job": "profession",

        "employer": "employer",
        "company": "employer",
        "workplace": "employer",

        "city": "city",
        "my city": "city",

        "pan": "pan_number",
        "pan number": "pan_number",
        "pan no": "pan_number",

        "aadhaar": "aadhaar_number",
        "aadhar": "aadhaar_number",
        "aadhaar number": "aadhaar_number",
        "aadhar number": "aadhaar_number",
        "aadhaar no": "aadhaar_number",
        "aadhar no": "aadhaar_number",

        "deposit": "last_deposit_amount",
        "last deposit": "last_deposit_amount",
        "deposit amount": "last_deposit_amount",
        "last deposit amount": "last_deposit_amount",
    }

    return aliases.get(q)


def is_customer_data_question(text):
    q = (text or "").lower().strip()

    # Short field-style questions are valid because a customer is already
    # selected in the application. This check happens AFTER the private
    # sharing/disclosure check in the chat-processing flow.
    if short_customer_field_from_question(text):
        return True

    # Normal, longer customer-data questions.
    patterns = [
        # Name
        r"\bwhat\s+is\s+my\s+name\b",
        r"\bwhat'?s\s+my\s+name\b",
        r"\bdo\s+you\s+know\s+my\s+name\b",
        r"\bwhat\s+was\s+my\s+name\b",
        r"\bwhat\s+is\s+my\s+first\s+name\b",
        r"\bwhat'?s\s+my\s+first\s+name\b",
        r"\bwhat\s+is\s+my\s+last\s+name\b",
        r"\bwhat'?s\s+my\s+last\s+name\b",

        # Phone / mobile
        r"\bwhat\s+is\s+my\s+mobile(?:\s+number)?\b",
        r"\bwhat'?s\s+my\s+mobile(?:\s+number)?\b",
        r"\bwhat\s+is\s+my\s+phone(?:\s+number)?\b",
        r"\bwhat'?s\s+my\s+phone(?:\s+number)?\b",
        r"\bdo\s+you\s+know\s+my\s+(?:mobile|phone)(?:\s+number)?\b",
        r"\bwhat\s+was\s+my\s+(?:mobile|phone)(?:\s+number)?\b",

        # Other customer records
        r"\bmy\s+account\s+number\b",
        r"\bmy\s+account\s+no\b",
        r"\bmy\s+customer\s+number\b",
        r"\bmy\s+favorite\b",
        r"\bmy\s+favourite\b",
        r"\bmy\s+father\b",
        r"\bmy\s+mother\b",
        r"\bmy\s+bank\b",
        r"\bmy\s+address\b",
        r"\bmy\s+email\b",
        r"\bmy\s+profession\b",
        r"\bmy\s+employer\b",
        r"\bmy\s+city\b",
        r"\bmy\s+deposit\b",
        r"\bhow\s+much\s+did\s+i\s+deposit\b",
        r"\bwhat\s+amount\s+did\s+i\s+deposit\b",
        r"\bmy\s+date\s+of\s+birth\b",
        r"\bmy\s+dob\b",
        r"\bmy\s+birthday\b",
    ]

    return any(
        re.search(pattern, q)
        for pattern in patterns
    )


# ============================================================
# MEMORY KEY FROM QUESTION
# ============================================================

def memory_key_from_question(text):

    q = text.lower()

    mapping = {

        "account_number": [
            "account number",
            "account no"
        ],

        "customer_number": [
            "customer number",
            "customer no"
        ],

        "favorite_movie": [
            "favorite movie",
            "favourite movie",
            "favorite film",
            "favourite film"
        ],

        "favorite_color": [
            "favorite color",
            "favourite color",
            "favorite colour",
            "favourite colour"
        ],

        "favorite_food": [
            "favorite food",
            "favourite food"
        ],

        "favorite_sport": [
            "favorite sport",
            "favourite sport"
        ],

        "father_name": [
            "father",
            "dad"
        ],

        "mother_name": [
            "mother",
            "mom",
            "mum"
        ],

        "bank_name": [
            "bank name",
            "which bank",
            "my bank"
        ],

        "address": [
            "address"
        ],

        "email": [
            "email"
        ],

        "profession": [
            "profession",
            "job"
        ],

        "city": [
            "city"
        ],

        "employer": [
            "employer",
            "company"
        ],

        "pan_number": [
            "pan number",
            "pan"
        ],

        "aadhaar_number": [
            "aadhaar",
            "aadhar"
        ],

        "last_deposit_amount": [
            "deposit",
            "deposited",
            "amount i deposited"
        ],
    }

    for key, phrases in mapping.items():

        if any(
            phrase in q
            for phrase in phrases
        ):

            return key

    return None


# ============================================================
# ANSWER CUSTOMER QUESTION LOCALLY
# ============================================================

def answer_customer_question(
    customer_id,
    question
):

    customer = get_customer(
        customer_id
    )

    q = question.lower().strip()
    short_field = short_customer_field_from_question(question)

    if customer:

        # ----------------------------------------------------
        # SHORT CUSTOMER QUESTIONS
        # ----------------------------------------------------
        # Because the customer is already selected, short questions
        # such as "name?", "phone number?", and "dob?" refer to
        # that selected customer's local record.
        # ----------------------------------------------------

        if short_field == "name":
            full_name = (
                f"{customer['first_name']} "
                f"{customer['last_name']}"
            ).strip()
            return full_name or NOT_FOUND_MESSAGE

        if short_field == "first_name":
            return customer["first_name"] or NOT_FOUND_MESSAGE

        if short_field == "last_name":
            return customer["last_name"] or NOT_FOUND_MESSAGE

        if short_field == "mobile":
            return customer["mobile"] or NOT_FOUND_MESSAGE

        if short_field == "dob":
            return customer["dob"] or NOT_FOUND_MESSAGE

        if short_field == "country":
            return customer["country"] or NOT_FOUND_MESSAGE

        # ----------------------------------------------------
        # NAME
        # ----------------------------------------------------

        name_question_patterns = [
            r"\bwhat\s+is\s+my\s+name\b",
            r"\bwhat'?s\s+my\s+name\b",
            r"\bdo\s+you\s+know\s+my\s+name\b",
            r"\bwhat\s+was\s+my\s+name\b",
        ]

        if any(
            re.search(pattern, q)
            for pattern in name_question_patterns
        ):
            full_name = (
                f"{customer['first_name']} "
                f"{customer['last_name']}"
            ).strip()

            return full_name or NOT_FOUND_MESSAGE

        if re.search(r"\bwhat\s+is\s+my\s+first\s+name\b", q) or \
           re.search(r"\bwhat'?s\s+my\s+first\s+name\b", q):
            return customer["first_name"] or NOT_FOUND_MESSAGE

        if re.search(r"\bwhat\s+is\s+my\s+last\s+name\b", q) or \
           re.search(r"\bwhat'?s\s+my\s+last\s+name\b", q):
            return customer["last_name"] or NOT_FOUND_MESSAGE

        # ----------------------------------------------------
        # MOBILE / PHONE
        # ----------------------------------------------------

        phone_question_patterns = [
            r"\bwhat\s+is\s+my\s+phone(?:\s+number)?\b",
            r"\bwhat'?s\s+my\s+phone(?:\s+number)?\b",
            r"\bwhat\s+is\s+my\s+mobile(?:\s+number)?\b",
            r"\bwhat'?s\s+my\s+mobile(?:\s+number)?\b",
            r"\bdo\s+you\s+know\s+my\s+phone(?:\s+number)?\b",
            r"\bdo\s+you\s+know\s+my\s+mobile(?:\s+number)?\b",
            r"\bwhat\s+was\s+my\s+phone(?:\s+number)?\b",
            r"\bwhat\s+was\s+my\s+mobile(?:\s+number)?\b",
        ]

        if any(
            re.search(pattern, q)
            for pattern in phone_question_patterns
        ):
            return customer["mobile"] or NOT_FOUND_MESSAGE

        # ----------------------------------------------------
        # DOB
        # ----------------------------------------------------

        if (
            "date of birth" in q
            or "dob" in q
            or "birthday" in q
        ):
            return customer["dob"] or NOT_FOUND_MESSAGE

        # ----------------------------------------------------
        # COUNTRY
        # ----------------------------------------------------

        if "country" in q:
            return customer["country"] or NOT_FOUND_MESSAGE

        # ----------------------------------------------------
        # FIRST NAME
        # ----------------------------------------------------

        if "first name" in q:
            return customer["first_name"] or NOT_FOUND_MESSAGE

        # ----------------------------------------------------
        # LAST NAME
        # ----------------------------------------------------

        if (
            "last name" in q
            or "surname" in q
        ):
            return customer["last_name"] or NOT_FOUND_MESSAGE

    # --------------------------------------------------------
    # PRIVATE MEMORY
    # --------------------------------------------------------

    key = short_field or memory_key_from_question(question)

    if key:
        value = get_customer_memory(
            customer_id,
            key
        )

        if value is not None:
            return value

    return NOT_FOUND_MESSAGE


# ============================================================
# GROQ
# ============================================================

def ask_groq(question):

    if not groq_client:

        return (
            "Groq is not configured. "
            "Please add GROQ_API_KEY to your .env file."
        )

    system_prompt = """
You are the TechNova Customer Support Agent.

Handle general, non-customer-specific questions.

Examples:

- How do I book a flight?
- How do I open a savings account?
- How do I deactivate an account?
- What documents are required?
- Explain a banking process.
- What movie is trending?
- Explain a general financial concept.

IMPORTANT PRIVACY RULE:

Private customer information is NOT provided to you.

Never invent, guess, or request customer-specific private data such as:

- phone number
- account number
- account balance
- deposits
- address
- DOB
- PAN
- Aadhaar
- customer-specific memories
- private customer records

The application handles those locally.

Answer general questions helpfully and naturally.
"""

    try:

        response = groq_client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": system_prompt
                },
                {
                    "role": "user",
                    "content": question
                }
            ],
            temperature=0.3
        )

        return response.choices[0].message.content

    except Exception as e:

        return (
            "I couldn't reach the AI service right now. "
            "Please try again.\n\n"
            f"Error: {e}"
        )


# ============================================================
# ATTACHMENTS
# ============================================================

ALLOWED_EXTENSIONS = {
    "jpg",
    "jpeg",
    "png",
    "webp",
    "pdf"
}


def save_uploaded_file(
    uploaded_file,
    customer_id,
    conversation_id,
    message_id
):

    extension = (
        uploaded_file.name
        .split(".")[-1]
        .lower()
    )

    if extension not in ALLOWED_EXTENSIONS:

        return None

    customer_folder = (
        UPLOAD_DIR
        / customer_id
        / conversation_id
    )

    customer_folder.mkdir(
        parents=True,
        exist_ok=True
    )

    safe_name = re.sub(
        r"[^a-zA-Z0-9._-]",
        "_",
        uploaded_file.name
    )

    filename = (
        f"{message_id}_"
        f"{uuid.uuid4().hex[:8]}_"
        f"{safe_name}"
    )

    file_path = (
        customer_folder
        / filename
    )

    with open(
        file_path,
        "wb"
    ) as file:

        file.write(
            uploaded_file.getbuffer()
        )

    db.execute(
        """
        INSERT INTO attachments (
            message_id,
            customer_id,
            conversation_id,
            original_name,
            stored_path,
            mime_type,
            created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            message_id,
            customer_id,
            conversation_id,
            uploaded_file.name,
            str(file_path),
            uploaded_file.type,
            now_iso()
        )
    )

    db.commit()

    return str(file_path)


def get_attachments(
    customer_id,
    conversation_id
):

    return db.execute(
        """
        SELECT *
        FROM attachments
        WHERE customer_id = ?
          AND conversation_id = ?
        ORDER BY id ASC
        """,
        (
            customer_id,
            conversation_id
        )
    ).fetchall()


# ============================================================
# SESSION STATE
# ============================================================

if "selected_customer_id" not in st.session_state:

    st.session_state.selected_customer_id = None


if "selected_conversation_id" not in st.session_state:

    st.session_state.selected_conversation_id = None


if "show_new_customer" not in st.session_state:

    st.session_state.show_new_customer = False


if "show_delete_customer" not in st.session_state:

    st.session_state.show_delete_customer = False


if "confirm_customer_delete" not in st.session_state:

    st.session_state.confirm_customer_delete = False


# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:

    st.markdown(
        """
        <div style="
            font-size:27px;
            font-weight:700;
            line-height:1.15;
        ">
        👤 Customer<br>
        Management
        </div>
        """,
        unsafe_allow_html=True
    )

    st.write("")

    # ========================================================
    # ADD NEW CUSTOMER
    # ========================================================

    if st.button(
        "＋ Add New Customer",
        width="stretch"
    ):

        st.session_state.show_new_customer = True
        st.session_state.show_delete_customer = False

        st.rerun()

    st.divider()

    # ========================================================
    # CREATE CUSTOMER
    # ========================================================

    if st.session_state.show_new_customer:

        st.subheader(
            "Create Customer"
        )

        current_year = datetime.now().year

        country_options = (
            ["Select country..."]
            + COUNTRY_NAMES
        )

        # ----------------------------------------------------
        # FIRST NAME
        # ----------------------------------------------------

        first_name = st.text_input(
            "First Name",
            placeholder="Enter first name",
            key="create_first_name"
        )

        # ----------------------------------------------------
        # LAST NAME
        # ----------------------------------------------------

        last_name = st.text_input(
            "Last Name",
            placeholder="Enter last name",
            key="create_last_name"
        )

        # ----------------------------------------------------
        # COUNTRY
        # ----------------------------------------------------

        country = st.selectbox(
            "Country",
            country_options,
            index=0,
            key="create_country"
        )

        if country != "Select country...":

            calling_code = COUNTRY_CODES.get(
                country,
                ""
            )

        else:

            calling_code = ""

        if calling_code:

            st.caption(
                f"Calling code: {calling_code}"
            )

        else:

            st.caption(
                "Select a country to see its calling code."
            )

        # ----------------------------------------------------
        # MOBILE
        # ----------------------------------------------------

        mobile_placeholder = (
            f"{calling_code} 9876543210"
            if calling_code
            else "Select country first"
        )

        mobile = st.text_input(
            "Mobile Number",
            placeholder=mobile_placeholder,
            key="create_mobile"
        )

        # ====================================================
        # DATE OF BIRTH
        # ====================================================

        st.markdown(
            "**Date of Birth**"
        )

        dob_col1, dob_col2, dob_col3 = st.columns(3)

        # ----------------------------------------------------
        # YEAR
        # ----------------------------------------------------

        year_options = (
            ["Select year..."]
            + [
                str(year)
                for year in range(
                    current_year,
                    1899,
                    -1
                )
            ]
        )

        with dob_col1:

            dob_year = st.selectbox(
                "Year",
                year_options,
                index=0,
                key="create_dob_year"
            )

        # ----------------------------------------------------
        # MONTH
        # ----------------------------------------------------

        month_options = (
            ["Select month..."]
            + [
                calendar.month_name[month]
                for month in range(
                    1,
                    13
                )
            ]
        )

        with dob_col2:

            dob_month = st.selectbox(
                "Month",
                month_options,
                index=0,
                key="create_dob_month"
            )

        # ----------------------------------------------------
        # DAY
        # ----------------------------------------------------

        if (
            dob_year != "Select year..."
            and
            dob_month != "Select month..."
        ):

            selected_year_for_days = int(
                dob_year
            )

            selected_month_for_days = list(
                calendar.month_name
            ).index(
                dob_month
            )

            max_day = calendar.monthrange(
                selected_year_for_days,
                selected_month_for_days
            )[1]

            day_options = (
                ["Select day..."]
                + [
                    str(day)
                    for day in range(
                        1,
                        max_day + 1
                    )
                ]
            )

        else:

            day_options = [
                "Select day..."
            ]

        # ----------------------------------------------------
        # IMPORTANT DOB FIX
        #
        # A different widget key is generated for every
        # Year + Month combination.
        #
        # Therefore changing the month cannot keep an old
        # day selected.
        # ----------------------------------------------------

        day_widget_key = (
            "create_dob_day_"
            f"{dob_year}_"
            f"{dob_month}"
        )

        with dob_col3:

            dob_day = st.selectbox(
                "Day",
                day_options,
                index=0,
                key=day_widget_key
            )

        st.write("")

        # ----------------------------------------------------
        # CREATE
        # ----------------------------------------------------

        create_clicked = st.button(
            "Create Customer",
            width="stretch"
        )

        # ----------------------------------------------------
        # CANCEL
        # ----------------------------------------------------

        cancel_clicked = st.button(
            "Cancel",
            width="stretch"
        )

        if cancel_clicked:

            st.session_state.show_new_customer = False

            st.rerun()

        # ====================================================
        # VALIDATION
        # ====================================================

        if create_clicked:

            errors = []

            if not first_name.strip():

                errors.append(
                    "First Name is required."
                )

            if not last_name.strip():

                errors.append(
                    "Last Name is required."
                )

            if country == "Select country...":

                errors.append(
                    "Country is required."
                )

            if not mobile.strip():

                errors.append(
                    "Mobile Number is required."
                )

            if dob_year == "Select year...":

                errors.append(
                    "Date of Birth Year is required."
                )

            if dob_month == "Select month...":

                errors.append(
                    "Date of Birth Month is required."
                )

            if dob_day == "Select day...":

                errors.append(
                    "Date of Birth Day is required."
                )

            if mobile.strip():

                mobile_digits = re.sub(
                    r"\D",
                    "",
                    mobile
                )

                if len(mobile_digits) < 5:

                    errors.append(
                        "Mobile Number is invalid."
                    )

            # ------------------------------------------------
            # SHOW ERRORS
            # ------------------------------------------------

            if errors:

                st.error(
                    "Please complete the following fields:"
                )

                for error in errors:

                    st.warning(
                        "• " + error
                    )

            # ------------------------------------------------
            # CREATE
            # ------------------------------------------------

            else:

                selected_year = int(
                    dob_year
                )

                selected_month = list(
                    calendar.month_name
                ).index(
                    dob_month
                )

                selected_day = int(
                    dob_day
                )

                dob_value = date(
                    selected_year,
                    selected_month,
                    selected_day
                ).isoformat()

                clean_mobile = mobile.strip()

                if not clean_mobile.startswith("+"):

                    clean_digits = re.sub(
                        r"\D",
                        "",
                        clean_mobile
                    )

                    clean_mobile = (
                        calling_code
                        + clean_digits
                    )

                new_customer_id_value = create_customer(
                    first_name,
                    last_name,
                    clean_mobile,
                    dob_value,
                    country
                )

                new_conversation_id_value = (
                    create_conversation(
                        new_customer_id_value
                    )
                )

                st.session_state.selected_customer_id = (
                    new_customer_id_value
                )

                st.session_state.selected_conversation_id = (
                    new_conversation_id_value
                )

                st.session_state.show_new_customer = False

                keys_to_clear = [
                    "create_first_name",
                    "create_last_name",
                    "create_country",
                    "create_mobile",
                    "create_dob_year",
                    "create_dob_month"
                ]

                for key in keys_to_clear:

                    if key in st.session_state:

                        del st.session_state[key]

                st.rerun()

    # ========================================================
    # CUSTOMER SELECTION / HISTORY
    # ========================================================

    else:

        customers = get_customers()

        if customers:

            customer_labels = {}

            for customer_item in customers:

                full_name = (
                    f"{customer_item['first_name']} "
                    f"{customer_item['last_name']}"
                ).strip()

                mobile_value = customer_item["mobile"] or ""

                if len(mobile_value) > 6:
                    masked_mobile = (
                        mobile_value[:3]
                        + "******"
                        + mobile_value[-3:]
                    )
                else:
                    masked_mobile = "******" if mobile_value else "Not available"

                label = (
                    f"{full_name} "
                    f"— {masked_mobile}"
                )

                customer_labels[
                    label
                ] = customer_item[
                    "customer_id"
                ]

            labels = list(
                customer_labels.keys()
            )

            current_customer_id = (
                st.session_state.selected_customer_id
            )

            selected_index = 0

            if current_customer_id:

                for index, label in enumerate(
                    labels
                ):

                    if (
                        customer_labels[label]
                        == current_customer_id
                    ):

                        selected_index = index
                        break

            selected_customer_label = st.selectbox(
                "Select Customer",
                labels,
                index=selected_index
            )

            selected_customer_id = (
                customer_labels[
                    selected_customer_label
                ]
            )

            # ------------------------------------------------
            # CUSTOMER SWITCH
            # ------------------------------------------------

            if (
                selected_customer_id
                != st.session_state.selected_customer_id
            ):

                st.session_state.selected_customer_id = (
                    selected_customer_id
                )

                st.session_state.show_delete_customer = False

                st.session_state.confirm_customer_delete = False

                cleanup_empty_chats(
                    selected_customer_id
                )

                customer_conversations = (
                    get_conversations(
                        selected_customer_id
                    )
                )

                if customer_conversations:

                    st.session_state.selected_conversation_id = (
                        customer_conversations[0][
                            "conversation_id"
                        ]
                    )

                else:

                    st.session_state.selected_conversation_id = (
                        create_conversation(
                            selected_customer_id
                        )
                    )

                st.rerun()

        else:

            st.info(
                "No customers created yet."
            )

        # ====================================================
        # CHAT HISTORY
        # ====================================================

        if st.session_state.selected_customer_id:

            current_customer_for_sidebar = (
                st.session_state.selected_customer_id
            )

            st.divider()

            st.markdown(
                "### 💬 Chat History"
            )

            # ------------------------------------------------
            # NEW CHAT
            # ------------------------------------------------

            current_conversation_id = (
                st.session_state.selected_conversation_id
            )

            if current_conversation_id:

                if st.button(
                    "＋ New Chat",
                    width="stretch"
                ):

                    current_messages = get_messages(
                        current_customer_for_sidebar,
                        current_conversation_id
                    )

                    if current_messages:

                        new_id = create_conversation(
                            current_customer_for_sidebar,
                            "New Chat"
                        )

                    else:

                        new_id = current_conversation_id

                    st.session_state.selected_conversation_id = (
                        new_id
                    )

                    st.rerun()

            # ------------------------------------------------
            # RECENT CHATS FOR THIS CUSTOMER ONLY
            # ------------------------------------------------

            recent_chats = get_conversations(
                current_customer_for_sidebar,
                limit=8
            )

            for chat in recent_chats:

                chat_id = chat[
                    "conversation_id"
                ]

                title = (
                    chat["title"]
                    or "New Chat"
                )

                if len(title) > 38:

                    title = (
                        title[:38]
                        + "..."
                    )

                if (
                    chat_id
                    == st.session_state.selected_conversation_id
                ):

                    icon = "●"

                else:

                    icon = "○"

                button_text = (
                    f"{icon} {title}"
                )

                if st.button(
                    button_text,
                    key=f"history_{chat_id}",
                    width="stretch"
                ):

                    # ----------------------------------------
                    # SECURITY CHECK
                    #
                    # This ensures the conversation belongs
                    # to the selected customer.
                    # ----------------------------------------

                    valid_chat = get_conversation(
                        chat_id,
                        current_customer_for_sidebar
                    )

                    if valid_chat:

                        st.session_state.selected_conversation_id = (
                            chat_id
                        )

                        st.rerun()

            # =================================================
            # DELETE CUSTOMER
            # =================================================

            st.divider()

            if st.button(
                "🗑 Delete Customer",
                width="stretch"
            ):

                st.session_state.show_delete_customer = True

                st.session_state.confirm_customer_delete = False

                st.rerun()

            # ------------------------------------------------
            # DELETE CONFIRMATION
            # ------------------------------------------------

            if st.session_state.show_delete_customer:

                st.warning(
                    "⚠️ This permanently deletes this customer "
                    "and all associated data."
                )

                st.caption(
                    "The customer's profile, chat history, "
                    "private memory, and uploaded files will "
                    "be permanently deleted. "
                    "This action cannot be undone."
                )

                confirm_delete = st.checkbox(
                    "I understand that this cannot be undone.",
                    key="confirm_customer_delete"
                )

                delete_col1, delete_col2 = st.columns(2)

                # ------------------------------------------------
                # CANCEL DELETE
                # ------------------------------------------------

                with delete_col1:

                    if st.button(
                        "Cancel",
                        key="cancel_customer_delete",
                        width="stretch"
                    ):

                        st.session_state.show_delete_customer = False

                        st.session_state.confirm_customer_delete = False

                        st.rerun()

                # ------------------------------------------------
                # PERMANENT DELETE
                # ------------------------------------------------

                with delete_col2:

                    if st.button(
                        "Delete Permanently",
                        type="primary",
                        disabled=not confirm_delete,
                        key="permanent_delete_customer",
                        width="stretch"
                    ):

                        permanently_delete_customer(
                            current_customer_for_sidebar
                        )

                        # ------------------------------------
                        # RESET EVERYTHING ASSOCIATED WITH
                        # THE DELETED CUSTOMER
                        # ------------------------------------

                        st.session_state.selected_customer_id = None

                        st.session_state.selected_conversation_id = None

                        st.session_state.show_delete_customer = False

                        st.session_state.confirm_customer_delete = False

                        st.rerun()


# ============================================================
# MAIN APPLICATION
# ============================================================

customer_id = (
    st.session_state.selected_customer_id
)

if not customer_id:

    st.title(
        "🧠 TechNova Customer Support Agent"
    )

    st.info(
        "Create or select a customer to begin."
    )

    st.stop()


customer = get_customer(
    customer_id
)

if not customer:

    st.error(
        "Customer not found."
    )

    st.stop()


# ============================================================
# ENSURE CONVERSATION BELONGS TO CUSTOMER
# ============================================================

cleanup_empty_chats(
    customer_id
)

conversation_id = (
    st.session_state.selected_conversation_id
)

conversation = None

if conversation_id:

    conversation = get_conversation(
        conversation_id,
        customer_id
    )

if not conversation:

    conversations = get_conversations(
        customer_id
    )

    if conversations:

        conversation_id = (
            conversations[0][
                "conversation_id"
            ]
        )

    else:

        conversation_id = create_conversation(
            customer_id
        )

    st.session_state.selected_conversation_id = (
        conversation_id
    )


# ============================================================
# HEADER
# ============================================================

st.title(
    "🧠 TechNova Customer Support Agent"
)

st.caption(
    "Private customer memory + general AI assistance"
)


# ============================================================
# CURRENT CUSTOMER DETAILS
# ============================================================

with st.expander(
    "👤 Current Customer Details",
    expanded=False
):

    col1, col2, col3, col4 = st.columns(4)

    with col1:

        st.write("**Name**")

        st.write(
            (
                f"{customer['first_name']} "
                f"{customer['last_name']}"
            ).strip()
        )

    with col2:

        st.write("**Mobile**")

        mobile_value = customer["mobile"] or ""

        # Mask the middle digits in the profile panel. The full
        # value is only returned by the local customer-data handler
        # when the customer explicitly asks for their own number.
        if len(mobile_value) > 6:
            masked_mobile = (
                mobile_value[:3]
                + "******"
                + mobile_value[-3:]
            )
        else:
            masked_mobile = "******" if mobile_value else "Not available"

        st.write(masked_mobile)

    with col3:

        st.write("**Country**")

        st.write(
            customer["country"]
        )

    with col4:

        st.write("**DOB**")

        st.write(
            customer["dob"]
        )


# ============================================================
# CHAT MESSAGES
# ============================================================

messages = get_messages(
    customer_id,
    conversation_id
)

for message in messages:

    role = message["role"]

    if role not in [
        "user",
        "assistant"
    ]:

        continue

    with st.chat_message(role):

        st.markdown(
            message["content"]
        )


# ============================================================
# ATTACHMENTS
# ============================================================

attachments = get_attachments(
    customer_id,
    conversation_id
)

if attachments:

    with st.expander(
        f"📎 Attachments ({len(attachments)})"
    ):

        for attachment in attachments:

            file_path = Path(
                attachment["stored_path"]
            )

            if file_path.exists():

                with open(
                    file_path,
                    "rb"
                ) as file:

                    file_data = file.read()

                st.download_button(
                    label=(
                        "📎 "
                        + attachment[
                            "original_name"
                        ]
                    ),
                    data=file_data,
                    file_name=attachment[
                        "original_name"
                    ],
                    mime=(
                        attachment["mime_type"]
                        or "application/octet-stream"
                    ),
                    key=(
                        "download_"
                        + str(
                            attachment["id"]
                        )
                    ),
                    width="stretch"
                )


# ============================================================
# CHAT INPUT
# ============================================================

chat_input = st.chat_input(
    "Type your message...",
    accept_file="multiple",
    file_type=[
        "jpg",
        "jpeg",
        "png",
        "webp",
        "pdf"
    ],
    max_upload_size=25
)


# ============================================================
# PROCESS CHAT
# ============================================================

if chat_input:

    user_text = getattr(
        chat_input,
        "text",
        ""
    )

    uploaded_files = getattr(
        chat_input,
        "files",
        []
    )

    user_text = (
        user_text or ""
    ).strip()

    # --------------------------------------------------------
    # FILE ONLY MESSAGE
    # --------------------------------------------------------

    if (
        not user_text
        and uploaded_files
    ):

        user_text = (
            "I uploaded "
            f"{len(uploaded_files)} file(s)."
        )

    if not user_text:

        st.stop()

    # --------------------------------------------------------
    # SAVE USER MESSAGE
    # --------------------------------------------------------

    message_id = save_message(
        customer_id,
        conversation_id,
        "user",
        user_text
    )

    # --------------------------------------------------------
    # SAVE FILES LOCALLY
    #
    # Files are NOT sent to Groq.
    # --------------------------------------------------------

    for uploaded_file in uploaded_files:

        save_uploaded_file(
            uploaded_file,
            customer_id,
            conversation_id,
            message_id
        )

    # --------------------------------------------------------
    # CUSTOMER UPDATE
    # --------------------------------------------------------

    memory_key, memory_value = (
        extract_customer_update(
            user_text
        )
    )

    if (
        memory_key
        and memory_value
    ):

        save_customer_memory(
            customer_id,
            memory_key,
            memory_value
        )

        readable_key = (
            memory_key
            .replace("_", " ")
        )

        reply = (
            f"Got it. I've updated your "
            f"{readable_key} in your private "
            f"customer record."
        )

    # --------------------------------------------------------
    # PRIVATE DATA SHARING / DISCLOSURE REQUEST
    # --------------------------------------------------------
    # IMPORTANT: This check MUST happen before the customer-data
    # lookup. Otherwise a sentence such as "share my phone number
    # to an LLM" could be mistaken for "what is my phone number?"
    # and the stored number could be returned to the chat.

    elif is_private_data_sharing_request(
        user_text
    ):

        reply = PRIVATE_DATA_SHARING_RESPONSE

    # --------------------------------------------------------
    # CUSTOMER-SPECIFIC QUESTION
    # --------------------------------------------------------

    elif is_customer_data_question(
        user_text
    ):

        reply = answer_customer_question(
            customer_id,
            user_text
        )

    # --------------------------------------------------------
    # GENERAL QUESTION
    # --------------------------------------------------------

    else:

        reply = ask_groq(
            user_text
        )

    # --------------------------------------------------------
    # SAVE ASSISTANT MESSAGE
    # --------------------------------------------------------

    save_message(
        customer_id,
        conversation_id,
        "assistant",
        reply
    )

    # --------------------------------------------------------
    # CHAT TITLE
    # --------------------------------------------------------

    all_messages = get_messages(
        customer_id,
        conversation_id
    )

    if len(all_messages) <= 2:

        title = re.sub(
            r"\s+",
            " ",
            user_text
        ).strip()

        if len(title) > 50:

            title = (
                title[:50]
                + "..."
            )

        update_conversation_title(
            conversation_id,
            customer_id,
            title
        )

    st.rerun()
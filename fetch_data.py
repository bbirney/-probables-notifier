import json
import os
import requests
import sqlite3
import sys
import yagmail
from collections import defaultdict
from datetime import datetime, timedelta, date
from dotenv import load_dotenv

MANUAL_RUN = '-m' in sys.argv

def create_html_table(records, table_title):
    # Group records by GameDate (stored in index 5 of each tuple)
    records_by_date = defaultdict(list)
    for record in records:
        records_by_date[record[5]].append(record)

    # Variable to hold all tables
    all_tables_html = ""

    # Generate a separate table for each GameDate
    for game_date, records in sorted(records_by_date.items()):
        # Parse the game_date to obtain the date and day name
        date_object = datetime.strptime(game_date, '%Y-%m-%dT%H:%M:%S')
        formatted_date = date_object.strftime('%Y-%m-%d')
        day_name = date_object.strftime('%A')

        # Update the HTML string to include day of the week
        html = f"<h2>{table_title} - {formatted_date} ({day_name})</h2>"
        html += "<table border='1'><tr><th>Name</th><th>Team</th><th>Opponent</th></tr>"

        for record in records:
            teamSPPlayerName = record[13]  # Index of teamSPPlayerName
            abbName = record[4]           # Index of AbbName
            opponentAbbName = record[11]  # Index of OpponentAbbName
            html += f"<tr><td>{teamSPPlayerName}</td><td>{abbName}</td><td>{'' if record[9] == 1 else '@'}{opponentAbbName}</td></tr>"

        html += "</table>"
        all_tables_html += html + "<br>"  # Add a line break between tables for better spacing

    return all_tables_html



def setupSqliteTable(cursor):
    # Create table and index if not exists
    cursor.execute('''CREATE TABLE IF NOT EXISTS game_info (
        TeamId INTEGER,
        League TEXT,
        Division TEXT,
        ShortName TEXT,
        AbbName TEXT,
        GameDate TEXT,
        dh INTEGER,
        AwayTeamId INTEGER,
        HomeTeamId INTEGER,
        isHome INTEGER,
        OpponentId INTEGER,
        OpponentAbbName TEXT,
        teamSPPlayerId TEXT,
        teamSPPlayerName TEXT,
        teamSPPlayerNameRoute TEXT,
        Throws TEXT,
        notes TEXT
    )''')
    cursor.execute('CREATE UNIQUE INDEX IF NOT EXISTS idx_teamdate ON game_info (TeamId, GameDate, dh);')

    # Clear data older than 7 days
    cursor.execute('DELETE FROM game_info WHERE GameDate < ?', (datetime.now() - timedelta(days=7),))

if __name__ == "__main__":

    load_dotenv()

    # API URL and headers
    url = os.getenv('PROBABLES_API_URL')
    headers = {
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.9",
        "DNT": "1",
        "If-Modified-Since": "Sat, 27 Apr 2024 17:29:33 GMT",
        "Priority": "u=1, i",
        "Referer": os.getenv('PROBABLES_REFERER_URL'),
        "Sec-CH-UA": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
        "Sec-CH-UA-Mobile": "?0",
        "Sec-CH-UA-Platform": "macOS",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin",
        "Sec-GPC": "1",
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    }

    # Establish connection to the SQLite database
    conn = sqlite3.connect('game_data.db')
    c = conn.cursor()

    setupSqliteTable(c)

    yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
    ten_days_later = (datetime.now() + timedelta(days=10)).strftime('%Y-%m-%d')
    query = f'''
    SELECT * FROM game_info
    WHERE date(GameDate) >= date('{yesterday}') AND date(GameDate) <= date('{ten_days_later}')
    '''

    # Execute the query and fetch the results
    existing_records = set(c.execute(query).fetchall())

    # Fetch data from the API
    response = requests.get(url, headers=headers)
    data = json.loads(response.text)

    # Insert or replace data into the database and track changes
    new_records = set()
    for entry in data:
        new_record = (entry['TeamId'], entry['League'], entry['Division'], entry['ShortName'], entry['AbbName'], entry['GameDate'], entry['dh'], entry['AwayTeamId'], entry['HomeTeamId'], entry['isHome'], entry['OpponentId'], entry['OpponentAbbName'], entry['teamSPPlayerId'], entry['teamSPPlayerName'], entry['teamSPPlayerNameRoute'], entry['Throws'], entry['notes'])
        c.execute('''REPLACE INTO game_info VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''', new_record)
        new_records.add(new_record)

    # Commit changes and close connection
    conn.commit()
    conn.close()

    # Calculate delta and generate HTML tables
    added_records = new_records - existing_records
    deleted_records = existing_records - new_records
    new_html = create_html_table(new_records, "Probables Grid")
    added_html = create_html_table(added_records, "Added")
    deleted_html = create_html_table(deleted_records, "Deleted")

    # Prepare to send the email
    emailAddress = os.getenv('PROBABLES_EMAIL_ADDRESS')

    # Register your OAuth credentials (only needed once)
    yag = yagmail.SMTP(emailAddress, oauth2_file="credentials.json")

    # Get the current time
    current_time = datetime.now().time()

    # Check if the time is between 7 AM and 9 AM
    rightTime = MANUAL_RUN or (current_time >= datetime.strptime('07:00', '%H:%M').time() and current_time <= datetime.strptime('09:00', '%H:%M').time())
    delta = rightTime or len(added_records) > 0 or len(deleted_records) > 0

    if delta or rightTime:
        # Sending the email
        yag.send(
            to=emailAddress, 
            subject=(date.today().strftime('%Y-%m-%d | ') + ("Probables Update" if delta else "Probables Report")),
            contents=new_html + "<hr>" + added_html + "<hr>" + deleted_html)

    print("Probables updated" + (" and email sent successfully." if delta or rightTime else ""))
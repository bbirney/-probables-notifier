import json
import os
import requests
import sqlite3
import sys
import yagmail
from collections import defaultdict
from datetime import datetime, timedelta, date
from dotenv import load_dotenv

def create_delta_table_old(records, table_title):
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

# Division mapping
DIVISIONS = {
    'AL East': ['BAL', 'BOS', 'NYY', 'TBR', 'TOR'],
    'AL Central': ['CHW', 'CLE', 'DET', 'KCR', 'MIN'],
    'AL West': ['HOU', 'LAA', 'OAK', 'SEA', 'TEX'],
    'NL East': ['ATL', 'MIA', 'NYM', 'PHI', 'WSN'],
    'NL Central': ['CHC', 'CIN', 'MIL', 'PIT', 'STL'],
    'NL West': ['ARI', 'COL', 'LAD', 'SDP', 'SFG']
}

def create_division_tables(records):
    team_division = {}
    for division, teams in DIVISIONS.items():
        for team in teams:
            team_division[team] = division
    
    division_records = defaultdict(list)
    for record in records:
        team = record[4]
        division_records[team_division[team]].append(record)

    html_output = ""
    for division, division_records in division_records.items():
        html_output += create_probables_table(division_records, division)
    return html_output

def create_probables_table(records, table_title):
    # Create a nested dictionary to store team by date with details
    team_date_details = defaultdict(lambda: defaultdict(list))

    # Populate the dictionary with records data
    for record in records:
        date_key = datetime.strptime(record[5], '%Y-%m-%dT%H:%M:%S').strftime('%A<br>%Y-%m-%d')
        team_key = record[4]
        opponent = record[11]
        player_name = record[13]
        is_home = '' if record[9] == 1 else '@'  # Home or away game
        detail = f"{is_home}{opponent}<br>{player_name}"
        team_date_details[team_key][date_key].append(detail)

    # Start the HTML string for the table
    html = f"<h2>{table_title}</h2>"
    html += "<table border='1'>"

    # Create header row with dates as column headings
    dates_sorted = sorted(set(date for team in team_date_details.values() for date in team.keys()))
    html += "<tr><th></th>" + "".join(f"<th>{date}</th>" for date in dates_sorted) + "</tr>"

    # Fill the table rows for each team
    for team, dates in team_date_details.items():
        html += f"<tr><td><b>{team}</b></td>"
        for date in dates_sorted:
            details = ",".join(dates[date]) if date in dates else ""
            html += f"<td>{details}</td>"
        html += "</tr>"

    # Close the table HTML
    html += "</table>"

    return html

def create_delta_table(records, table_title):
    # Group records by GameDate (stored in index 5 of each tuple)
    records_by_date = defaultdict(list)
    for record in records:
        records_by_date[record[5]].append(record)

    # Variable to hold all tables
    all_tables_html = ""

    # Determine the table background color based on the table title
    if "added" in table_title.lower():
        table_style = "background-color: #ccffcc;"  # Light green
    elif "deleted" in table_title.lower():
        table_style = "background-color: #ffcccc;"  # Light red
    else:
        table_style = ""

    # Generate a separate table for each GameDate
    for game_date, records in sorted(records_by_date.items()):
        # Parse the game_date to obtain the date and day name
        date_object = datetime.strptime(game_date, '%Y-%m-%dT%H:%M:%S')
        formatted_date = date_object.strftime('%Y-%m-%d')
        day_name = date_object.strftime('%A')

        # Update the HTML string to include day of the week and table style
        html = f"<h2>{table_title} - {formatted_date} ({day_name})</h2>"
        html += f"<table border='1' style='{table_style}'><tr><th>Name</th><th>Team</th><th>Opponent</th></tr>"

        for record in records:
            teamSPPlayerName = record[13]  # Index of teamSPPlayerName
            abbName = record[4]           # Index of AbbName
            opponentAbbName = record[11]  # Index of OpponentAbbName
            html += f"<tr><td>{teamSPPlayerName}</td><td>{abbName}</td><td>{'' if record[9] == 1 else '@'}{opponentAbbName}</td></tr>"

        html += "</table>"
        all_tables_html += html + "<br>"  # Add a line break between tables for better spacing

    return all_tables_html

def setup_db(cursor):
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

def fetch_data_api():
    response = requests.get(os.getenv('PROBABLES_API_URL'), headers={
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
    })
    data = json.loads(response.text)
    return data

def fetch_data_db(cursor):
    query = f'''
        SELECT * 
          FROM game_info
         WHERE date(GameDate) >= date('{(datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')}') /* yesterday */
           AND date(GameDate) <= date('{(datetime.now() + timedelta(days=10)).strftime('%Y-%m-%d')}') /* 10 days from now */
    '''
    return set(cursor.execute(query).fetchall())

def upsert_data(cursor, data):
    new_records = set()
    for entry in data:
        new_record = (
            entry['TeamId'], 
            entry['League'], 
            entry['Division'], 
            entry['ShortName'], 
            entry['AbbName'], 
            entry['GameDate'], 
            entry['dh'], 
            entry['AwayTeamId'], 
            entry['HomeTeamId'], 
            entry['isHome'], 
            entry['OpponentId'], 
            entry['OpponentAbbName'], 
            entry['teamSPPlayerId'], 
            entry['teamSPPlayerName'], 
            entry['teamSPPlayerNameRoute'], 
            entry['Throws'], 
            entry['notes'])
        cursor.execute('''REPLACE INTO game_info VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''', new_record)
        new_records.add(new_record)
    return new_records

def send_email(html_content, subject):
    # Prepare to send the email
    emailAddress = os.getenv('PROBABLES_EMAIL_ADDRESS')

    # Register your OAuth credentials (only needed once)
    yag = yagmail.SMTP(emailAddress, oauth2_file="credentials.json")
    
    # Sending the email
    yag.send(
        to=emailAddress, 
        subject=(date.today().strftime('%Y-%m-%d | ') + subject),
        contents=html_content)

if __name__ == "__main__":

    MANUAL_RUN = '-m' in sys.argv

    load_dotenv()

    # Establish connection to the SQLite database
    conn = sqlite3.connect('game_data.db')
    c = conn.cursor()

    setup_db(c)

    # Execute the query and fetch the results
    existing_records = fetch_data_db(c)

    # Fetch data
    data = fetch_data_api()

    # Persist to db
    new_records = upsert_data(c, data)

    # Commit changes and close connection
    conn.commit()
    conn.close()

    # Calculate delta and generate HTML tables
    added_records = new_records - existing_records
    deleted_records = existing_records - new_records
    new_html = create_division_tables(new_records)
    added_html = create_delta_table(added_records, "Added")
    deleted_html = create_delta_table(deleted_records, "Deleted")

    # Get the current time
    current_time = datetime.now().time()

    # Check if the time is between 7 AM and 9 AM
    rightTime = MANUAL_RUN or (current_time >= datetime.strptime('07:00', '%H:%M').time() and current_time <= datetime.strptime('09:00', '%H:%M').time())
    delta = rightTime or len(added_records) > 0 or len(deleted_records) > 0

    if delta or rightTime:
        send_email(new_html + "<hr>" + added_html + "<hr>" + deleted_html, ("Probables Update" if delta else "Probables Report"))

    print("Probables updated" + (" and email sent successfully." if delta or rightTime else ""))
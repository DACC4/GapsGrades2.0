import requests
from bs4 import BeautifulSoup
import urllib.parse
import re
import codecs
import telegram
import json
import os
import asyncio

username = os.environ.get("HESSO_USERNAME")
password = os.environ.get("HESSO_PASSWORD")

api_key = os.environ.get("TELEGRAM_API_KEY")
chat_id = os.environ.get("TELEGRAM_CHAT_ID")

def get_gaps_cookies():
    # Login
    cookies = requests.post("https://gaps.heig-vd.ch/consultation/index.php", 
                            data={"login": username, "password": password, "submit": "Enter"}
                            ).cookies
    return cookies

def decode_unicode_escapes(text):
    return codecs.escape_decode(bytes(text, "utf-8").decode("unicode_escape"))[0].decode("utf-8").split('\n', 1)[0]

def note_message(note):
    return "\n" + note["description"] + " : [" + note["note"] + "] (average " + note["average"] + ")"

def parse_grades(grades_html):
    # Repair broken HTML
    grades_html = urllib.parse.unquote(grades_html)
    regex = re.compile("\+:\"@.*@(.*)@.*@\"")
    grades_html = regex.match(grades_html).group(1)
    grades_html = grades_html.replace("\\\"", "\"")
    grades_html = grades_html.replace("\\/", "/")

    # Parse HTML using 
    parsed_html = BeautifulSoup(grades_html, "lxml")

    notes = {}
    currentIndex = ""
    currentSubIndex = ""

    #For each cell in the table
    for row in parsed_html.body.find("table").find_all("tr"):
        # New branch
        if row.find("td", {"class": "bigheader"}):
            regex = re.compile("(.*) - .* : (.*)")
            regmatch = regex.match(row.find("td", {"class": "bigheader"}).text)

            currentIndex = decode_unicode_escapes(regmatch.group(1))
            notes[currentIndex] = {}
            notes[currentIndex]["name"] = decode_unicode_escapes(regmatch.group(1))
            notes[currentIndex]["average"] = decode_unicode_escapes(regmatch.group(2))
            continue
        
        # New sub branch
        if row.find("td", {"class": "edge"}):
            regex = re.compile("(.*)moyenne : (.*)poids : (.*)")
            regmatch = regex.match(row.find("td", {"class": "edge"}).text)

            currentSubIndex = decode_unicode_escapes(regmatch.group(1))
            notes[currentIndex][currentSubIndex] = {}
            notes[currentIndex][currentSubIndex]["average"] = decode_unicode_escapes(regmatch.group(2))
            notes[currentIndex][currentSubIndex]["coeff"] = decode_unicode_escapes(regmatch.group(3))
            notes[currentIndex][currentSubIndex]["notes"] = []
            continue
        if row.find("td", {"class": "odd"}):
            regex = re.compile("(.*)moyenne : (.*)poids : (.*)")
            regmatch = regex.match(row.find("td", {"class": "odd"}).text)

            currentSubIndex = decode_unicode_escapes(regmatch.group(1))
            notes[currentIndex][currentSubIndex] = {}
            notes[currentIndex][currentSubIndex]["average"] = decode_unicode_escapes(regmatch.group(2))
            notes[currentIndex][currentSubIndex]["coeff"] = decode_unicode_escapes(regmatch.group(3))
            notes[currentIndex][currentSubIndex]["notes"] = []
            continue

        # New note
        if row.find("td", {"class": "bodyCC"}):
            cells = row.find_all("td")

            notes[currentIndex][currentSubIndex]["notes"].append({
                "date": decode_unicode_escapes(cells[0].text),
                "description": currentIndex + " > " + currentSubIndex + " > " + decode_unicode_escapes(cells[1].text),
                "average": decode_unicode_escapes(cells[2].text),
                "coeff": decode_unicode_escapes(cells[3].text),
                "note": decode_unicode_escapes(cells[4].text)
            })
            continue
    
    return notes

def compare_notes(notes):
    if(os.path.isfile("notes.json")):
        with open("notes.json", "r") as f:
            old_data = json.load(f)
    else:
        print("No data file")
        old_data = notes

    if(old_data != notes):
        print("Changes detected")
        message = "[GAPS] Modification detected !"

        for branch in notes:
            # If the branch doesn't exist in the old data or if the branch is different
            if (branch not in old_data) or old_data[branch] != notes[branch]:
                for subbranch in notes[branch]:
                    # If the subbranch is the name or the average => skip
                    if subbranch == "name" or subbranch == "average":
                        continue

                    if branch not in old_data:
                        message += "\nNew branch: " + branch
                        break

                    if subbranch not in old_data[branch]:
                        message += "\nNew subbranch: " + subbranch
                        # Add all the notes of the subbranch
                        for note in notes[branch][subbranch]["notes"]:
                            message += note_message(note)
                        break

                    # If the subbranch is different
                    if(old_data[branch][subbranch] != notes[branch][subbranch]):
                        # Try to find the note that changed
                        for note in notes[branch][subbranch]["notes"]:
                            if note not in old_data[branch][subbranch]["notes"]:
                                message += note_message(note)
    
        return message
    else:
        return ""

def send_message(message):
    print(message)
    bot = telegram.Bot(token=api_key)
    asyncio.run(bot.send_message(chat_id=chat_id, text=message))

def save_notes(notes):
    with open("notes.json", "w") as f:
        json.dump(notes, f)

'''
-----------------------------------------------------------------------------------------------
'''

# Grades
grades_html = requests.post("https://gaps.heig-vd.ch/consultation/controlescontinus/consultation.php?idst=17845", 
                       cookies=cookies,
                       data={"rs": "smartReplacePart", "rsargs": "[\"result\",\"result\",null,null,null,null]"}
                       ).text

# Parse and compare to stored data
grades = parse_grades(grades_html)
message = compare_notes(grades)

# Send message if new grades
if message == ""
    print("No changes")
else:
    send_message(message)

# Save new grades
save_notes(notes)
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
        message = "[GAPS - Grades] Modification detected !"

        for branch in notes:
            # If the branch doesn't exist in the old data or if the branch is different
            if (branch not in old_data) or old_data[branch] != notes[branch]:
                for subbranch in notes[branch]:
                    # If the subbranch is the name or the average => skip
                    if subbranch == "name" or subbranch == "average":
                        continue

                    if branch not in old_data:
                        message += "\nNew branch: " + branch
                        # Add all the notes of the branch
                        for sub in notes[branch]:
                            if sub == "name" or sub == "average":
                                continue
                            for note in notes[branch][sub]["notes"]:
                                message += note_message(note)
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

def parse_bulletin(bulletin_html):
    # Parse HTML using 
    parsed_html = BeautifulSoup(bulletin_html, "lxml")

    bulletin = {}
    currentIndex = ""

     #For each cell in the table
    for row in parsed_html.body.find("table", {"id": "record_table"}).find_all("tr"):
        # Header, skip
        if "bulletin_header_row" in row.attrs['class']:
            continue

        # End line, skip
        if "total-credits-row" in row.attrs['class']:
            continue

        # Module
        if "bulletin_module_row" in row.attrs['class']:
            cells = [a.text for a in row.find_all("td")]

            title = cells[0]
            name = cells[1]
            passed = cells[2]
            grade = cells[4]

            currentIndex = title
            bulletin[currentIndex] = {}
            bulletin[currentIndex]["title"] = title
            bulletin[currentIndex]["name"] = name
            bulletin[currentIndex]["passed"] = passed
            bulletin[currentIndex]["grade"] = grade
            bulletin[currentIndex]["units"] = {}
            continue

        # Unit
        if "bulletin_unit_row" in row.attrs['class']:
            cells = [a.text for a in row.find_all("td")]

            name = re.match("(.*)<br>", cells[1])
            subbranches = re.findall("([A-Z][a-z]*) \((\d*%)\) : (\d\.?\d?)", cells[1])
            
            title = cells[0]
            name = name
            grades = {}
            grade = cells[4]

            for a in subbranches:
                name = a[0]
                percentage = a[1]
                g = a[2]

                i = "{} ({})".format(name, percentage)

                grades[i] = g


            if len(subbranches) != 0:
                bulletin[currentIndex]["units"][title] = {
                    'title': title,
                    'name': name,
                    'grade': grade,
                    'grades': grades
                }

            continue
        
    
    return bulletin

def compare_bulletin(bulletin):
    if(os.path.isfile("bulletin.json")):
        with open("bulletin.json", "r") as f:
            old_data = json.load(f)
    else:
        print("No data file")
        old_data = bulletin

    if(old_data != bulletin):
        print("Changes detected")
        message = "[GAPS - Bulletin] Modification detected !"

        for module in bulletin:
            if (module in old_data) and bulletin[module] == old_data[module]:
                continue

            message += module_message(bulletin[module])
            for a in bulletin[module]['units']:
                message += unit_message(bulletin[module]['units'][a])
    
        return message
    else:
        return ""

def module_message(module):
    return "\n💠 {} : {} ({})".format(module['title'], module['passed'], module['grade'])

def unit_message(unit):
    tr = "\n   ♦️ {} : {} (".format(unit['title'], unit['grade'])
    i = 0
    for a in unit['grades']:
        tr += "{} {}".format(a, unit['grades'][a])
        i += 1
        if i < len(unit['grades']):
            tr += " | "
    tr += ")"
    return tr

def save_bulletin(bulletin):
    with open("bulletin.json", "w") as f:
        json.dump(bulletin, f)

'''
-----------------------------------------------------------------------------------------------
'''

cookies = get_gaps_cookies()

# Grades
grades_html = requests.post("https://gaps.heig-vd.ch/consultation/controlescontinus/consultation.php?idst=17845", 
                       cookies=cookies,
                       data={"rs": "smartReplacePart", "rsargs": "[\"result\",\"result\",null,null,null,null]"}
                       ).text

# Parse and compare to stored data
grades = parse_grades(grades_html)
message = compare_notes(grades)

# Send message if new grades
if message == "":
    print("No changes")
else:
    send_message(message)

# Save new grades
save_notes(grades)

'''
-----------------------------------------------------------------------------------------------
'''

# Bulletin
bulletin_html = requests.post("https://gaps.heig-vd.ch/consultation/notes/bulletin.php?id=17845", 
                       cookies=cookies,
                       ).text

# Parse and compare to stored data
bulletin = parse_bulletin(bulletin_html)

message = compare_bulletin(bulletin)

# Send message if new bulletin
if message == "":
    print("No changes")
else:
    send_message(message)

# Save new bulletin
save_bulletin(bulletin)
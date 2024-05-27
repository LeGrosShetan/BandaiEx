# Imports #
import enum

import requests
import pandas as pd
from bs4 import BeautifulSoup
import os
import platform
import subprocess

## Time delay enum
class TimeDelay(enum.Enum):
    Hourly = 0
    Daily = 1
    Monthly = 2

### Settings
ScriptRefreshTimeDelay = TimeDelay.Monthly

# Retrieves text from a soup's div tag and tries to return a float out of it.
# Returns 0 if an error occurs
def makeFloatOfPercent(soupDiv):
    try :
        return float(soupDiv.text.strip("%"))/100
    except:
        return 0
    
# Not in use - Retrieves header of main page (current month + year) to use as a file name (ex:"April_2024")
def makeFileName():
    page = requests.get("https://store.steampowered.com/hwsurvey")
    pageSoup = BeautifulSoup(page.text, 'html5lib')

    ### Extracting HWS' header so we can use it as our file's name
    mainHeaderRaw = pageSoup.find('div', {"id":"main_stats_header"})
    mainHeaderRaw.span.extract()
    return mainHeaderRaw.text.strip().replace(' ', '_')

# Retrieves main stats from steam's hardware survey website and exports them as a CSV.
# Takes in a parameter, scriptPath which will be used to store out CSV in path : scriptPath/Exports
def scrapeMainHardwareSurvey(scriptPath):
    print("Beginning Main HWS scrape")
    
    page = requests.get("https://store.steampowered.com/hwsurvey")
    pageSoup = BeautifulSoup(page.text, 'html5lib')
    hwsSoup = pageSoup.find('div', {"id": "hws_main"})
    
    mainStatsSoup = hwsSoup.find('div', {"id":"main_stats"})
    
    ### Creating Pandas dataframe as well as an index to properly allocate entries
    hwsDf = pd.DataFrame(columns=["Category", "Group", "Entry", "Usage_%", "Evolution_%"])
    locIndex=0

    hwsCategories = mainStatsSoup.findAll('div',{"class":"stats_row"}, recursive=False)
    hwsCategoriesHeaders = [HWSStat.find('div',{"class":"stats_col_left"}).text.strip() for HWSStat in hwsCategories]

    for index,hwsCategory in enumerate(hwsCategories):
        categoryFirstStatsEntries = hwsCategory.findNext('div',{"class":"stats_row_details"}).findChildren('div',{"class":"stats_col_mid data_row"})
        for firstStatEntry in categoryFirstStatsEntries:
            entryName = firstStatEntry.text.strip()
            RowPercent = firstStatEntry.findNextSibling("div")
            entryPercent = makeFloatOfPercent(RowPercent)
            entryChangePercent = makeFloatOfPercent(RowPercent.findNextSibling("div"))
            entryGroupRow = firstStatEntry.findPreviousSibling("div", {"class":"stats_row"})
            if entryGroupRow:
                entryGroup = entryGroupRow.find('div', {"class":"stats_col_mid"}).text.strip()
            else:
                entryGroup = None

            hwsDf.loc[locIndex] = [hwsCategoriesHeaders[index], entryGroup, entryName, entryPercent, entryChangePercent]
            locIndex += 1

    print("Finished Main HWS scrape, exporting...")
    if not os.path.exists(scriptPath + "/Exports/"):
        os.mkdir(scriptPath + "/Exports/")
    hwsDf.to_csv(scriptPath + "/Exports/" + "MainSurvey.csv", sep=';', index=False)
    print("Finished data export of Main HWS")

# Retrieves Videocard-related stats from steam's hardware survey website and exports them as a CSV.
# Takes in a parameter, scriptPath which will be used to store out CSV in path : scriptPath/Exports
def scrapeHardwareSurveyVideocard(scriptPath):
    print("Beginning Videocard HWS scrape")
    
    page = requests.get("https://store.steampowered.com/hwsurvey/videocard/")
    pageSoup = BeautifulSoup(page.text, 'html5lib')
    hwsStatsSoup = pageSoup.find('div', {"id": "sub_stats"})

    ### Creating Pandas dataframe as well as an index to properly allocate entries
    mainHWSTitles = ["Subcategory", "Entry", "Month-4", "Month-3", "Month-2", "Month-1", "Month", "MonthChange_%"]
    #months = hwsStatsSoup.findChildren('div', {"class":lambda value: value and value.startswith("substats_col_month")}, limit=5)
    #monthsTitles = [MonthTitle.text.strip() for MonthTitle in months]
    #mainHWSTitles += monthsTitles
    #mainHWSTitles += ["MonthChange_%"]
    
    hwsDf = pd.DataFrame(columns=mainHWSTitles)
    locIndex=0
    
    for childDiv in hwsStatsSoup.findChildren('div', {"class": lambda value: value and value.startswith("substats_row")}):
        subcategory = childDiv.findPreviousSibling('div', {"class":"substats_col_left col_header"}).text.strip()
        ChildStatsRaw = childDiv.findChildren("div", {"class":lambda value: value and value.startswith("substats_col")}, limit=7)
        floatArray = [makeFloatOfPercent(ChildStatsRaw[i+1]) for i in range(len(ChildStatsRaw)-1)]
        hwsDf.loc[locIndex] = [subcategory, ChildStatsRaw[0].text.strip()] + floatArray
        locIndex += 1

    print("Finished Videocard HWS scrape, exporting...")
    if not os.path.exists(scriptPath + "/Exports/"):
        os.mkdir(scriptPath + "/Exports/")
    hwsDf.to_csv(scriptPath + "/Exports/" + "VideocardSurvey.csv", sep=';', index=False)
    print("Finished data export of Videocard HWS")

# Tries to determine OS type of running computer
def determine_os():
    os_type = platform.system()
    if os_type == 'Linux':
        return 'Linux'
    elif os_type == 'Darwin':
        return 'macOS'
    elif os_type == 'Windows':
        return 'Windows'
    else:
        return 'Unknown'

# Checks if a cron or task exists and makes one if there is none initialized
def check_need_create_scheduled_job(script_path, taskName, scriptRefreshTimeDelay):
    os_type = determine_os()
    if os_type in ['Linux', 'macOS']:
        if not cron_job_exists(script_path):
            create_scheduled_job(script_path, "", scriptRefreshTimeDelay)

    if os_type == 'Windows':
        if not task_scheduler_job_exists(taskName):
            create_scheduled_job(script_path, taskName, scriptRefreshTimeDelay)

    else:
        print("Unsupported operating system.")

# Creates a cron (Linux or MacOS) or a task (Windows) to automate scraping
def create_scheduled_job(script_path, task_name, scriptRefreshTimeDelay):
    os_type = determine_os()

    if os_type in ['Linux', 'macOS']:
        cron_command = f''
        # Define the cron job command
        if scriptRefreshTimeDelay == TimeDelay.Hourly:
            cron_command = f'(crontab -l ; echo "@hourly /usr/bin/python3 {script_path}") | crontab -'
        elif scriptRefreshTimeDelay == TimeDelay.Daily:
            cron_command = f'(crontab -l ; echo "0 0 * * * /usr/bin/python3 {script_path}") | crontab -'
        elif scriptRefreshTimeDelay == TimeDelay.Monthly:
            cron_command = f'(crontab -l ; echo "0 0 1 * * /usr/bin/python3 {script_path}") | crontab -'

        if cron_command != f'':
            subprocess.run(cron_command, shell=True, check=True)
            print("Cron job created successfully.")

    elif os_type == 'Windows':
        task_command = f''
        # Define the Task Scheduler command
        if scriptRefreshTimeDelay == TimeDelay.Hourly:
            task_command = f'schtasks /create /tn "{task_name}" /tr "python {script_path}" /sc hourly /f'
        elif scriptRefreshTimeDelay == TimeDelay.Daily:
            task_command = f'schtasks /create /tn "{task_name}" /tr "python {script_path}" /sc daily /st 00:00 /f'
        elif scriptRefreshTimeDelay == TimeDelay.Monthly:
            task_command = f'schtasks /create /tn "{task_name}" /tr "python {script_path}" /sc monthly /mo 1 /d 1 /st 00:00 /f'

        if task_command != f'':
            subprocess.run(task_command, shell=True, check=True)
            print("Task Scheduler job created successfully.")

    else:
        print("Unsupported operating system.")

# Checks if a cron exists by this script's path
def cron_job_exists(script_path):
    result = subprocess.run('crontab -l', shell=True, capture_output=True, text=True)
    return script_path in result.stdout

# Checks if a task exists by its name
def task_scheduler_job_exists(task_name):
    result = subprocess.run(f'schtasks /query /tn "{task_name}"', shell=True, capture_output=True, text=True)
    return result.returncode == 0

if __name__ == '__main__':
    script_path = os.path.dirname(os.path.realpath(__file__))
    
    check_need_create_scheduled_job(script_path, "SteamHardwareSurveyAutomatedScript", ScriptRefreshTimeDelay)
    
    scrapeMainHardwareSurvey(script_path)
    scrapeHardwareSurveyVideocard(script_path)
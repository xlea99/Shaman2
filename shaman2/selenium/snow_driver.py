from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select
from selenium.webdriver.common.keys import Keys
import time
from shaman2.selenium.browser import Browser
from shaman2.common.logger import log
from shaman2.common.paths import paths
from shaman2.common.config import mainConfig
from shaman2.utilities.async_sound import playsoundAsync
from shaman2.utilities.shaman_utils import convertServiceIDFormat,naturalPause
from shaman2.data_storage.snow_storage import SnowTask


class SnowDriver:

    # Simple init method.
    def __init__(self, browserObject: Browser):
        logMessage = "Initialized new SnowDriver object"
        self.browser = browserObject

        if ("Snow" in self.browser.tabs.keys()):
            self.browser.closeTab("Snow")
            logMessage += ", and closed existing Verizon tab."
        else:
            logMessage += "."
        self.browser.openNewTab("Snow")

        self.__lastUsedTaskFrame = None

        log.info(logMessage)

    # Attempts to log in to SNow, if not already logged in
    def logInToSnow(self):
        self.browser.switchToTab("Snow")

        if("sysco.service-now" in self.browser.current_url):
            return True
        else:
            self.browser.get("https://sysco.service-now.com")

            emailInputFieldXPath = "//input[@type='email']"
            emailInputField = self.browser.searchForElement(by=By.XPATH,value=emailInputFieldXPath,timeout=30)
            emailInputField.send_keys(mainConfig["authentication"]["snowEmail"])
            emailInputField.send_keys(Keys.ENTER)
            naturalPause()

            netIDInputFieldXPath = "//input[@id='userInput']"
            netIDInputField = self.browser.searchForElement(by=By.XPATH,value=netIDInputFieldXPath,timeout=30)
            netIDInputField.send_keys(mainConfig["authentication"]["snowUser"])
            netIDInputField.send_keys(Keys.ENTER)
            naturalPause()

            passInputFieldXPath = "//input[@id='password']"
            passInputField = self.browser.searchForElement(by=By.XPATH,value=passInputFieldXPath,timeout=30)
            naturalPause()
            passInputField.send_keys(mainConfig["authentication"]["snowPass"])
            naturalPause()
            passInputField.send_keys(Keys.ENTER)
            naturalPause()

            # Now, we look for the "Stay Signed In" page.
            staySignedInHeadingXPath = "//div[normalize-space(text())='Stay signed in?']"
            self.browser.searchForElement(by=By.XPATH,value=staySignedInHeadingXPath,timeout=30,testClickable=True,testLiteralClick=True)
            yesButtonXPath = "//input[@type='submit'][@value='Yes']"
            yesButton = self.browser.searchForElement(by=By.XPATH,value=yesButtonXPath,timeout=3)
            yesButton.click()
            naturalPause()

            # Now we wait for the "Dashboards Overview" header to load, to signify that we're fully signed in.
            dashboardsOverviewHeaderCSS = ".experience-title"
            self.browser.searchForElement(by=By.CSS_SELECTOR,value=dashboardsOverviewHeaderCSS,timeout=60,
                                                                     shadowRootStack=[{"by": By.XPATH,"value": "//*[@global-navigation-config]"},
                                                                                      {"by": By.CSS_SELECTOR,"value": "sn-polaris-layout"},
                                                                                      {"by": By.CSS_SELECTOR,"value": "sn-polaris-header"}],
                                                                     extraElementTests=[lambda el: el.text.strip() == "Dashboards Overview"],raiseError=True)

    # Nav method for Favorites menu options.
    def navToFavoritesMenuOption(self,option : str):
        self.browser.switchToTab("Snow")

        favoritesTabCSS = "[id$='b682fe1c3133010cbd77096e940dd18']"
        favoritesTab = self.browser.searchForElement(by=By.CSS_SELECTOR,value=favoritesTabCSS,timeout=10,
                                                                     shadowRootStack=[{"by": By.XPATH,"value": "//*[@global-navigation-config]"},
                                                                                      {"by": By.CSS_SELECTOR,"value": "sn-polaris-layout"},
                                                                                      {"by": By.CSS_SELECTOR,"value": "sn-polaris-header"}],
                                                                     extraElementTests=[lambda el: el.get_attribute("aria-label") == "Favorites"])
        favoritesTab.click()
        naturalPause()

        favoritesMenuItemCSS = ".label"
        favoritesMenuItem = self.browser.searchForElement(by=By.CSS_SELECTOR,value=favoritesMenuItemCSS,timeout=10,
                                                                     shadowRootStack=[{"by": By.XPATH,"value": "//*[@global-navigation-config]"},
                                                                                      {"by": By.CSS_SELECTOR,"value": "sn-polaris-layout"},
                                                                                      {"by": By.CSS_SELECTOR,"value": "sn-polaris-header"},
                                                                                      {"by": By.CSS_SELECTOR,"value": "sn-polaris-menu.can-animate","extraElementTests": [lambda el: el.get_attribute("aria-label").strip() == "Unpinned Favorites menu"]},
                                                                                      {"by": By.CSS_SELECTOR,"value": "sn-collapsible-list","withSubElement": {"by": By.CSS_SELECTOR,"value": ".label", "extraElementTests": [lambda el: el.text.strip() == option]}}],
                                                                     extraElementTests=[lambda el: el.text.strip() == option],raiseError=True)
        favoritesMenuItem.click()
        naturalPause()

    # Nav method to pull up a specific request number.
    def navToRequest(self,requestNumber : str):
        self.browser.switchToTab("Snow")
        self.navToFavoritesMenuOption("Home")


        # Sometimes the stupid search button has trouble clearing. So, we perform an "intelligent" search here.
        for i in range(3):
            searchBarCSS = "#sncwsgs-typeahead-input"
            searchBar = self.browser.searchForElement(by=By.CSS_SELECTOR,value=searchBarCSS,timeout=10,testClickable=True,
                                                                     shadowRootStack=[{"by": By.XPATH,"value": "//*[@global-navigation-config]"},
                                                                                      {"by": By.CSS_SELECTOR,"value": "sn-polaris-layout"},
                                                                                      {"by": By.CSS_SELECTOR,"value": "sn-polaris-header"},
                                                                                      {"by": By.CSS_SELECTOR,"value": "sn-search-input-wrapper"},
                                                                                      {"by": By.CSS_SELECTOR,"value": "sn-component-workspace-global-search-typeahead"}],raiseError=True)
            clearedSearch = False
            for i in range(5):
                searchBar.clear()
                time.sleep(1)
                if(searchBar.get_attribute("value").strip() == ""):
                    clearedSearch = True
                    break
                else:
                    time.sleep(1)
                    continue
            # This means the page is freaking out, just refresh.
            if(clearedSearch):
                naturalPause()
                searchBar.send_keys(requestNumber)
                searchBar.send_keys(Keys.ENTER)
                naturalPause()
                break
            else:
                self.browser.refresh()
                continue

        # Now, we search for an exact match.
        exactMatch = self.browser.searchForElement(by=By.CSS_SELECTOR,value="div.global-search-records:nth-child(1)",timeout=10,testClickable=True,
                                                                     shadowRootStack=[{"by": By.XPATH,"value": "//*[@global-navigation-config]"},
                                                                                      {"by": By.CSS_SELECTOR,"value": "#item-snCanvasAppshellMain"},
                                                                                      {"by": By.CSS_SELECTOR,"value": ".sn-canvas-appshell-main > *:first-child > *:first-child"},
                                                                                      {"by": By.CSS_SELECTOR,"value": "sn-canvas-main"},
                                                                                      {"by": By.CSS_SELECTOR,"value": "sn-canvas-screen:nth-of-type(2)"},
                                                                                      {"by": By.CSS_SELECTOR,"value": ".sn-canvas-screen > *:first-child > *:first-child"},
                                                                                      {"by": By.CSS_SELECTOR,"value": "#item-search_result_wrapper_1"},
                                                                                      {"by": By.CSS_SELECTOR,"value": "sn-component-workspace-global-search-tab"}])
        if(exactMatch):
            exactMatch.click()
            naturalPause()
        # Sometimes, SNow randomly goes straight to the task. Here we test for a task frame to see if we're already there,
        # if we couldn't locate the exactMatch header.
        else:
            if(self.browser.searchForElement(by=By.CSS_SELECTOR, value="#gsft_main", timeout=5,
                                      shadowRootStack=[{"by": By.XPATH, "value": "//*[@global-navigation-config]"}])):
                return True
            else:
                error = RuntimeError(f"Tried to navigate to request '{requestNumber}', but couldn't locate it!")
                log.error(error)
                raise error


    #region === Task Management ===

    # This helper method handles scoping into the task frame of the (assumed currently open) task, simply
    # returning true if it's already open.
    def Tasks_ScopeToTaskFrame(self):
        # Test if the previous taskFrame is still valid.
        if(self.__lastUsedTaskFrame):
            try:
                self.browser.switch_to.frame(self.__lastUsedTaskFrame)
                return True
            except Exception as e:
                pass
        self.browser.switch_to.default_content()
        self.browser.switchToTab("Snow")
        # Otherwise, find and switch the browser to the task's iframe.
        taskFrame = self.browser.searchForElement(by=By.CSS_SELECTOR,value="#gsft_main",timeout=10,
                                                                     shadowRootStack=[{"by": By.XPATH,"value": "//*[@global-navigation-config]"}],raiseError=True)
        self.browser.switch_to.frame(taskFrame)
        self.__lastUsedTaskFrame = taskFrame
        return True

    # This method assumes a task is currently open, and it reads the full task into a task object.
    def Tasks_ReadFullTask(self):
        self.browser.switchToTab("Snow")

        newTask = SnowTask()
        # Scope to task frame first
        self.Tasks_ScopeToTaskFrame()

        # Read relevant information
        newTask["Number"] = self.browser.find_element(by=By.XPATH,value="//input[@id='sys_readonly.sc_task.number']").get_attribute("value")
        newTask["AssignmentGroup"] = self.browser.find_element(by=By.XPATH,value="//input[@id='sys_display.sc_task.assignment_group']").get_attribute("value")
        newTask["AssignedTo"] = self.browser.find_element(by=By.XPATH,value="//input[@id='sys_display.sc_task.assigned_to']").get_attribute("value")
        newTask["Request"] = self.browser.find_element(by=By.XPATH,value="//input[@id='sc_task.request_label']").get_attribute("value")
        newTask["RequestItem"] = self.browser.find_element(by=By.XPATH,value="//input[@id='sys_display.sc_task.request_item']").get_attribute("value")
        newTask["Priority"] = Select(self.browser.find_element(by=By.XPATH,value="//select[@id='sc_task.priority']")).first_selected_option.text
        newTask["State"] = Select(self.browser.find_element(by=By.XPATH,value="//select[@id='sc_task.state']")).first_selected_option.text
        newTask["ShortDescription"] = self.browser.find_element(by=By.XPATH,value="//input[@id='sc_task.short_description']").get_attribute("value")
        newTask["Description"] = self.browser.find_element(by=By.XPATH,value="//textarea[@id='sc_task.description']").get_attribute("value")

        # Read all activities
        allActivitiesXPath = "//ul[contains(@class,'activities-form')]/li"
        allActivities = self.browser.find_elements(by=By.XPATH,value=allActivitiesXPath)
        for i in range(len(allActivities)):
            createdBy = self.browser.find_element(by=By.XPATH,value=f"{allActivitiesXPath}[{i+1}]//span[@class='sn-card-component-createdby']").text
            timestamp = self.browser.find_element(by=By.XPATH,value=f"{allActivitiesXPath}[{i+1}]//div[@class='date-calendar']").text
            baseContent = self.browser.find_element(by=By.XPATH,value=f"{allActivitiesXPath}[{i+1}]/div[3]").text

            # Check if there's an attached email and, if so, temporarily connect to iframe and add it to the activity.
            showEmailButton = self.browser.searchForElement(by=By.XPATH,value=f"{allActivitiesXPath}[{i+1}]//a[@action-type='show-email']")
            if(showEmailButton):
                showEmailButton.click()

                emailFrameXPath = f"{allActivitiesXPath}[{i+1}]//iframe[@class='card activity-stream-email-iframe']"
                emailFrame = self.browser.searchForElement(by=By.XPATH,value=emailFrameXPath,timeout=10)
                self.browser.switch_to.frame(emailFrame)
                emailContent = self.browser.searchForElement(by=By.XPATH,value="//body",timeout=10).text
                self.browser.switch_to.default_content()
                self.browser.switchToTab("Snow")

                # Scope back to task frame.
                self.Tasks_ScopeToTaskFrame()

                hideEmailButton = self.browser.searchForElement(by=By.XPATH,value=f"{allActivitiesXPath}[{i + 1}]//a[@action-type='hide-email']",timeout=10)
                hideEmailButton.click()
            else:
                emailContent = None

            newTask.addActivity(createdBy=createdBy,timestamp=timestamp,baseContent=baseContent,emailContent=emailContent)

        # Return the browser to default frame.
        self.browser.switch_to.default_content()
        self.browser.switchToTab("Snow")
        naturalPause()
        return newTask

    # Various write methods for each relevant part of the task
    def Tasks_WriteAssignmentGroup(self,assignmentGroup):
        self.browser.switchToTab("Snow")
        self.Tasks_ScopeToTaskFrame()

        assignmentGroupInputXPath = "//input[@id='sys_display.sc_task.assignment_group']"
        assignmentGroupInput = self.browser.find_element(by=By.XPATH, value=assignmentGroupInputXPath)
        assignmentGroupInput.clear()
        assignmentGroupInput.send_keys(assignmentGroup)

        self.browser.switch_to.default_content()
        self.browser.switchToTab("Snow")
    def Tasks_WriteAssignedTo(self,assignedTo):
        self.browser.switchToTab("Snow")
        self.Tasks_ScopeToTaskFrame()

        assignmentToInputXPath = "//input[@id='sys_display.sc_task.assigned_to']"
        assignmentToInput = self.browser.find_element(by=By.XPATH, value=assignmentToInputXPath)
        assignmentToInput.clear()
        assignmentToInput.send_keys(assignedTo)

        self.browser.switch_to.default_content()
        self.browser.switchToTab("Snow")
    def Tasks_WriteState(self,state):
        self.browser.switchToTab("Snow")
        self.Tasks_ScopeToTaskFrame()
        state = state.strip()

        validStates = ["On Hold - With Customer","Pending","Open","Work in Progress",
                       "Closed Complete","Closed Incomplete","Closed Skipped"]
        if(state not in validStates):
            error = ValueError(f"Tried to set task's State to invalid value: '{state}'")
            log.error(error)
            raise error

        stateDropdownXPath = "//select[@id='sc_task.state']"
        stateDropdown = Select(self.browser.find_element(by=By.XPATH, value=stateDropdownXPath))
        stateDropdown.select_by_visible_text(state)

        self.browser.switch_to.default_content()
        self.browser.switchToTab("Snow")
    def Tasks_WritePriority(self,priority):
        self.browser.switchToTab("Snow")
        self.Tasks_ScopeToTaskFrame()
        priority = priority.strip()

        validPriorities = ["-- None --","1 - Critical","2 - High","3 - Moderate","4 - Low","5 - Planning"]
        if(priority not in validPriorities):
            error = ValueError(f"Tried to set task's Priority to invalid value: '{priority}'")
            log.error(error)
            raise error

        priorityDropdownXPath = "//select[@id='sc_task.priority']"
        priorityDropdown = Select(self.browser.find_element(by=By.XPATH, value=priorityDropdownXPath))
        priorityDropdown.select_by_visible_text(priority)

        self.browser.switch_to.default_content()
        self.browser.switchToTab("Snow")
    # Method to write/add a note to the task (and one for the special "additional note").
    def Tasks_WriteNote(self,noteContent):
        self.browser.switchToTab("Snow")
        self.Tasks_ScopeToTaskFrame()

        workNotesTextAreaXPath = "//textarea[@data-stream-text-input='work_notes'][@id='activity-stream-textarea']"
        workNotesTextArea = self.browser.searchForElement(by=By.XPATH,value=workNotesTextAreaXPath,timeout=3,scrollIntoView=True)
        workNotesTextArea.clear()
        workNotesTextArea.send_keys(noteContent)

        # Now, click "Post"
        postButtonXPath = "//button[contains(@ng-click,'postJournalEntryForCurrent')][normalize-space(text())='Post']"
        postButton = self.browser.searchForElement(by=By.XPATH,value=postButtonXPath,timeout=3,scrollIntoView=True)
        postButton.click()

        self.browser.switch_to.default_content()
        self.browser.switchToTab("Snow")
    def Tasks_WriteAdditionalNote(self,noteContent):
        self.browser.switchToTab("Snow")
        self.Tasks_ScopeToTaskFrame()

        additionalNoteTextAreaXPath = "//textarea[@data-stream-text-input='comments'][@id='activity-stream-comments-textarea']"
        additionalNoteTextArea = self.browser.searchForElement(by=By.XPATH,value=additionalNoteTextAreaXPath,timeout=5,scrollIntoView=True)
        additionalNoteTextArea.clear()
        additionalNoteTextArea.send_keys(noteContent)

        # We don't need to click post, since it gets auto-posted on update for a Completed ticket.
        self.browser.switch_to.default_content()
        self.browser.switchToTab("Snow")

    # This method simply adds the given tag to the task.
    def Tasks_AddTag(self,tagName):
        self.browser.switchToTab("Snow")
        self.Tasks_ScopeToTaskFrame()

        # First, open the "more options" submenu
        moreOptionsMenuXPath = "//button[@id='toggleMoreOptions']"
        moreOptionsMenu = self.browser.searchForElement(by=By.XPATH,value=moreOptionsMenuXPath,timeout=3)
        moreOptionsMenu.click()

        # Then click on "Add Tag". This process sometimes fails, so try it a few times.
        successfullyAddedTag = False
        for i in range(5):
            try:
                addTagButtonXPath = "//button[@id='tags_menu']"
                addTagInputXPath = "//li[@class='tagit-new']/input"
                addTagButton = self.browser.searchForElement(by=By.XPATH,value=addTagButtonXPath,timeout=5,testClickable=True)
                self.browser.safeClick(element=addTagButton,retryClicks=True,clickDelay=5,timeout=60,
                                       successfulClickCondition=lambda b: b.searchForElement(by=By.XPATH,value=addTagInputXPath))
                naturalPause()

                # Then, write the target tag.
                addTagInput = self.browser.searchForElement(by=By.XPATH,value=addTagInputXPath,timeout=5,testClickable=True)
                addTagInput.clear()
                addTagInput.send_keys(tagName[:5])
                naturalPause()
                addTagInput.send_keys(tagName[5:])

                # Finally, click on the correct tag.
                foundTagOptionXPath = f"//li[@class='ui-menu-item']/a[normalize-space(text())='{tagName.strip()}']"
                foundTagOption = self.browser.searchForElement(by=By.XPATH,value=foundTagOptionXPath,timeout=5,testClickable=True)
                foundTagOption.click()
                successfullyAddedTag = True
            except Exception as e:
                time.sleep(1)
                continue

        if(not successfullyAddedTag):
            error = RuntimeError(f"Could not add tag '{tagName}' after 5 attempts.")
            log.error(error)
            raise error

        self.browser.switch_to.default_content()
        self.browser.switchToTab("Snow")
    # This method simply updates the currently open task.
    def Tasks_Update(self):
        self.browser.switchToTab("Snow")
        self.Tasks_ScopeToTaskFrame()

        updateButtonXPath = "//span[@class='navbar_ui_actions']/button[@id='sysverb_update']"
        updateButton = self.browser.searchForElement(by=By.XPATH,value=updateButtonXPath,timeout=5)
        updateButton.click()

        self.browser.switch_to.default_content()
        self.browser.switchToTab("Snow")

    #endregion === Task Management ===
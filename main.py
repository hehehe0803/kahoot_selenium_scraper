import re
import time
from datetime import date
import pandas as pd
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from tqdm import tqdm

COLLECTION_URLS_DF_PATH = './collections.csv'
QUIZ_URLS_DF_PATH = './quiz_urls.csv'
QUIZ_QUESTIONS_DF_PATH = 'quiz_data@20-10-2021.csv'
DRIVER_PATH = '/home/hehehe0803/Desktop/kahoot_scraper_selenium/driver/chromedriver'


class KahootSeleniumScraper(object):

    def __init__(self):
        self.collections_df = pd.read_csv(COLLECTION_URLS_DF_PATH)
        self.quiz_urls_df = pd.read_csv(QUIZ_URLS_DF_PATH)
        self.quiz_df = pd.DataFrame(
            columns=['quiz_title', 'question_number', 'question_type', 'question', 'answer', 'true_false']
        )

        self.options = webdriver.ChromeOptions()
        self.options.headless = True
        self.driver = webdriver.Chrome(executable_path=DRIVER_PATH, options=self.options)
        self.driver.delete_all_cookies()

    def check_exists_by_id(self, element, id):
        try:
            element.find_element_by_id(id)
        except NoSuchElementException:
            return False
        return True

    def add_row(self, title, question_number, question_type, question_detail, answer, true_false):
        self.quiz_df = self.quiz_df.append({'quiz_title': title, 'question_number': question_number,
                                            'question_type': question_type, 'question': question_detail,
                                            'answer': answer, 'true_false': true_false},
                                           ignore_index=True)

    def crawl_subjects(self, url):
        collections_df = pd.DataFrame(columns=['title', 'url'])

        self.driver.delete_all_cookies()
        self.driver.get(url)
        page = self.driver.find_element_by_css_selector("div[class='layout__inner layout_explore_container'")
        collections = page.find_elements_by_class_name('layout__item')

        for collection in collections:
            try:
                on_click = collection.find_element_by_xpath('./div').get_attribute('onclick')
                if on_click is None:
                    href = collection.find_element_by_tag_name('a').get_attribute('href')
                    title = collection.find_element_by_tag_name('h1').text
                    collections_df = collections_df.append({'title': title, 'url': href}, ignore_index=True)
                else:
                    href = re.findall('http\S+[a-z0-9]', on_click)[0]
                    title = collection.find_element_by_tag_name('h1').text
                    collections_df = collections_df.append({'title': title, 'url': href}, ignore_index=True)
            except Exception as e:
                print(on_click.get_attribute('innerHTML'))

        collections_df.to_csv('./collections.csv', index=False)

    def crawl_profile_url(self, url):

        self.driver.delete_all_cookies()
        self.driver.get(url)

        try:
            button = WebDriverWait(self.driver, 20).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, 'span[role="button"]')))
            button.click()

            # wait for quizzes to load
            time.sleep(5)
        except TimeoutException:
            pass

        quizzes = self.driver.find_elements_by_css_selector('a[data-functional-selector="discover-card__title"]')
        for quiz in quizzes:
            title = quiz.get_attribute('textContent')
            quiz_url = quiz.get_attribute('href')
            self.quiz_urls_df = self.quiz_urls_df.append({'title': title, 'url': quiz_url}, ignore_index=True)

        self.quiz_urls_df.to_csv('./quiz_urls.csv', index=False)

    def click_button_collection(self):
        droppable_content = WebDriverWait(self.driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, 'ol[data-rbd-droppable-id="droppable"]'))
        )
        while True:
            try:
                button = WebDriverWait(droppable_content, 5).until(
                    EC.element_to_be_clickable((By.XPATH, './button')))
                button.click()
            except TimeoutException:
                break

    def crawl_collection_url(self, url):
        self.driver.delete_all_cookies()
        self.driver.get(url)

        self.click_button_collection()

        quiz_buttons = self.driver.find_elements_by_css_selector('button[data-functional-selector="course'
                                                                 '-details__kahoot-card"]')
        for i in range(len(quiz_buttons)):
            while True:
                try:
                    self.click_button_collection()
                    quiz_button = self.driver.find_elements_by_css_selector('button[data-functional-selector="course'
                                                                            '-details__kahoot-card"]')[i]
                    break
                except Exception as e:
                    self.driver.get(url)

            title = quiz_button.find_element_by_tag_name('h4').get_attribute('textContent')

            webdriver.ActionChains(self.driver).move_to_element(quiz_button).click(quiz_button).perform()
            quiz_url = self.driver.current_url

            self.quiz_urls_df = self.quiz_urls_df.append({'title': title, 'url': quiz_url}, ignore_index=True)
            self.driver.back()
            time.sleep(5)

        self.quiz_urls_df.to_csv('./quiz_urls.csv', index=False)

    def crawl_quiz_urls(self):
        for index, row in tqdm(self.collections_df.iterrows(), total=len(self.collections_df),
                               desc='Crawling Quiz urls'):
            if row['url'].split('/')[-2] == 'collection':
                self.crawl_collection_url(row['url'])
            else:
                self.crawl_profile_url(row['url'])

    def crawl_data(self, url):
        self.driver.delete_all_cookies()
        self.driver.get(url)

        # click show details
        WebDriverWait(self.driver, 5).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, 'button[data-functional-selector='
                                                         '"question-list__group-toggle"]'))
        ).click()

        title = self.driver.find_element_by_css_selector(
            'div[data-functional-selector="kahoot-detail__title"]').get_attribute('textContent')

        content = self.driver.find_elements_by_css_selector('div[aria-label="Question block"]')

        for section in content:
            question, options = [div for div in section.find_elements_by_xpath('./div')]

            question = question.find_elements_by_tag_name('span')
            question_number = question[0].text
            question_type = question[2].text
            question_detail = question[3].text

            # print(question_number, question_type)

            options = options.find_elements_by_xpath('./div/div')

            # if question_type == 'Slide' then pass
            if question_type in ('Slide', 'Word cloud', 'Poll', 'Open-ended', 'Brainstorm'):
                pass

            # logic for quiz and true/false
            elif question_type != 'Puzzle':
                for option in options:
                    answer, true_false = option.find_elements_by_xpath('./div')
                    # print(answer, true_false)

                    # try for text answer
                    try:
                        answer = answer.find_element_by_xpath('./span').get_attribute('textContent')
                        true_false = 'right' if self.check_exists_by_id(true_false, 'correct-icon') else 'wrong'
                        self.quiz_df = self.quiz_df.append({'quiz_title': title, 'question_number': question_number,
                                                            'question_type': question_type, 'question': question_detail,
                                                            'answer': answer, 'true_false': true_false},
                                                           ignore_index=True)

                    # try for image answer
                    except NoSuchElementException:
                        answer = answer.find_element_by_css_selector('div[role="presentation"]').get_attribute('title')
                        true_false = 'right' if self.check_exists_by_id(true_false, 'correct-icon') else 'wrong'
                        self.quiz_df = self.quiz_df.append({'quiz_title': title, 'question_number': question_number,
                                                            'question_type': question_type, 'question': question_detail,
                                                            'answer': answer, 'true_false': true_false},
                                                           ignore_index=True)

            # logic for puzzle
            else:
                for option in options[0].find_elements_by_xpath('./div/div')[1].find_elements_by_xpath('./p'):
                    answer = option.get_attribute('textContent')
                    true_false = 'right'
                    # print(answer, true_false)
                    self.quiz_df = self.quiz_df.append({'quiz_title': title, 'question_number': question_number,
                                                        'question_type': question_type, 'question': question_detail,
                                                        'answer': answer, 'true_false': true_false},
                                                       ignore_index=True)

    def execute(self):
        for index, row in tqdm(self.quiz_urls_df.iterrows(), total=len(self.quiz_urls_df), desc='Processing urls'):
            try:
                self.crawl_data(row['url'])
            except Exception as e:
                import traceback;
                traceback.print_exc();
                self.driver.save_screenshot(f'error_{row["url"]}.png')
                continue

        self.quiz_df.to_csv(f'./quiz_data@{date.today().strftime("%d-%m-%Y")}.csv', index=False)

        self.driver.quit()


if __name__ == '__main__':
    df = pd.read_csv(QUIZ_QUESTIONS_DF_PATH)
    df_groupby = df.groupby(['quiz_title', 'question_number'])
    print(df_groupby)

import requests
import pandas as pd
from collections import OrderedDict
import io
import os
from dotenv import load_dotenv
from flask import Flask, render_template, request, send_file
app = Flask(__name__)
load_dotenv()  # take environment variables from .env
global logged_in
logged_in = False


def process_data(df_form, rescue_number=None):
    rescues = df_form['rescue_number'].unique().tolist()
    if not rescues:
        rescues = [1]
    if not rescue_number:
        rescue_number = max(rescues)
    rescues = ['total'] + rescues
    if rescue_number != 'total':
        df_form = df_form[df_form['rescue_number'] == rescue_number]

    # save locally, in case you want to download
    df_form.to_excel("rescue_data.xlsx")

    total = len(df_form)
    males = len(df_form[df_form['gender'] == 'male'])
    females = len(df_form[df_form['gender'] == 'female'])
    df_minors = df_form[(df_form['age'] != '18_50') & (df_form['age'] != '50p')]
    df_adults = df_form[(df_form['age'] == '18_50') | (df_form['age'] == '50p')]

    # minors
    minors = len(df_minors)
    minors_male = len(df_minors[df_minors['gender'] == 'male'])
    minors_female = len(df_minors[df_minors['gender'] == 'female'])

    # unaccompanied minors
    df_unacc_minors = df_minors[df_minors['accompanied'] == 'no']
    df_unacc_minors = df_unacc_minors.append(df_minors[(df_minors['accompanied'] == 'yes') &
                                                       (df_minors['accompanied_by_who'] != 'parent')],
                                             ignore_index=True)
    unacc_minors = len(df_unacc_minors)
    unacc_minors_male = len(df_unacc_minors[df_unacc_minors['gender'] == 'male'])
    unacc_minors_female = len(df_unacc_minors[df_unacc_minors['gender'] == 'female'])
    unacc_pregnant_minors = len(df_unacc_minors[(df_unacc_minors['gender'] == 'female') &
                                                (df_unacc_minors['pregnant_breastfeeding'] == 'yes')])

    # unaccompanied women
    df_women = df_adults[df_adults['gender'] == 'female']
    df_unacc_women = df_women[df_women['accompanied'] == 'no']
    unacc_women = len(df_unacc_women)
    unacc_pregnant_women = len(df_unacc_women[df_unacc_women['pregnant_breastfeeding'] == 'yes'])

    age_value_counts = df_form['age'].value_counts().to_dict()
    age_label_dict = {"u1": "Less than 1 year",
                      "1_4": "1-4 years",
                      "5_17": "5-17 years",
                      "18_50": "18-50 years",
                      "50p": "More than 50 years"}
    age_group_counts = OrderedDict()
    for age_label, age_text in age_label_dict.items():
        if age_label in age_value_counts.keys():
            age_group_counts[age_text] = age_value_counts[age_label]

    country_counts = df_form['country'].value_counts().to_dict()
    country_counts = {k: v for k, v in sorted(country_counts.items(), key=lambda item: item[1], reverse=True)}

    return render_template('data.html',
                           total=total,
                           males=males,
                           females=females,
                           minors=minors,
                           minors_male=minors_male,
                           minors_female=minors_female,
                           unacc_minors=unacc_minors,
                           unacc_minors_male=unacc_minors_male,
                           unacc_minors_female=unacc_minors_female,
                           unacc_pregnant_minors=unacc_pregnant_minors,
                           unacc_women=unacc_women,
                           unacc_pregnant_women=unacc_pregnant_women,
                           age_value_counts=age_group_counts,
                           country_counts=country_counts,
                           rescues=rescues,
                           selected_rescue=rescue_number)


def get_data():
    # get data from kobo
    headers = {'Authorization': f'Token {os.getenv("TOKEN")}'}
    data_request = requests.get(
        f'https://kobonew.ifrc.org/api/v2/assets/{os.getenv("ASSET")}/data.json',
        headers=headers)
    data = data_request.json()
    if 'results' in data.keys():
        df_form = pd.DataFrame(data['results'])
    else:
        df_form = pd.DataFrame(columns=['rescue_number', 'gender', 'age', 'accompanied',
                                        'accompanied_by_who', 'pregnant_breastfeeding', 'country'])
    return df_form


@app.route("/data", methods=['GET', 'POST'])
def default_page():
    if request.method == 'GET':
        login_page()
    if request.method == 'POST':
        if request.form['password'] == 'password':
            global logged_in
            logged_in = True
            df_form = get_data()
            return process_data(df_form)
        else:
            return "wrong password"


@app.route("/dataupdate", methods=['GET', 'POST'])
def update_rescue():
    if request.method == 'GET':
        login_page()
    if request.method == 'POST':
        global logged_in
        if logged_in:
            df_form = get_data()
            return process_data(df_form, request.form['rescue'])
        else:
            return login_page()


@app.route("/download", methods=['GET', 'POST'])
def download_data():
    myio = io.BytesIO()
    with open("rescue_data.xlsx", 'rb') as f:
        data = f.read()
    myio.write(data)
    myio.seek(0)
    return send_file(myio, as_attachment=True, attachment_filename="rescue_data.xlsx")


@app.route("/")
def login_page():
    global logged_in
    logged_in = False
    return render_template('home.html')


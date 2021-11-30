import requests
import pandas as pd
from collections import OrderedDict
import io
import os
from dotenv import load_dotenv
# from azure.storage.blob import BlobServiceClient
from flask import Flask, render_template, request, send_file
app = Flask(__name__)
load_dotenv()  # take environment variables from .env


def process_data(df_form, rescue_number=None):

    if 'rescue_number' in df_form.columns:
        rescues = df_form['rescue_number'].unique().tolist()
    else:
        rescues = []
    if not rescues:
        rescues = [1]
    if not rescue_number:
        rescue_number = max(rescues)
    rescues = [str(x) for x in rescues]
    rescues = ['total'] + rescues
    if 'rescue_number' in df_form.columns:
        if rescue_number != 'total':
            df_form = df_form[df_form['rescue_number'] == rescue_number]
    else:
        df_form = pd.DataFrame()

    total = len(df_form)
    males, females, minors, minors_male, minors_female = 0, 0, 0, 0, 0
    pregnant, pregnant_women, pregnant_minors = 0, 0, 0
    unacc_minors, unacc_minors_male, unacc_minors_female, unacc_pregnant_minors = 0, 0, 0, 0
    unacc_women, unacc_pregnant_women = 0, 0

    if 'gender' in df_form.columns:
        males = len(df_form[df_form['gender'] == 'male'])
        females = len(df_form[df_form['gender'] == 'female'])
        df_minors = df_form[(df_form['age'] != '18_50') & (df_form['age'] != '50p')]
        df_adults = df_form[(df_form['age'] == '18_50') | (df_form['age'] == '50p')]

        # minors
        minors = len(df_minors)
        minors_male = len(df_minors[df_minors['gender'] == 'male'])
        minors_female = len(df_minors[df_minors['gender'] == 'female'])

        # pregnant
        if 'pregnant' in df_form.columns:
            pregnant = len(df_form[df_form['pregnant'] == 'yes'])
        if 'pregnant' in df_adults.columns:
            pregnant_women = len(df_adults[df_adults['pregnant'] == 'yes'])
        if 'pregnant' in df_minors.columns:
            pregnant_minors = len(df_minors[df_minors['pregnant'] == 'yes'])

        # unaccompanied minors
        df_unacc_minors = df_minors[df_minors['accompanied'] == 'no']
        if 'accompanied_by_who' in df_minors.columns:
            df_unacc_minors = df_unacc_minors.append(df_minors[(df_minors['accompanied'] == 'yes') &
                                                               (df_minors['accompanied_by_who'] != 'parent')],
                                                     ignore_index=True)
        unacc_minors = len(df_unacc_minors)
        unacc_minors_male = len(df_unacc_minors[df_unacc_minors['gender'] == 'male'])
        unacc_minors_female = len(df_unacc_minors[df_unacc_minors['gender'] == 'female'])
        if 'pregnant' in df_unacc_minors.columns:
            unacc_pregnant_minors = len(df_unacc_minors[(df_unacc_minors['gender'] == 'female') &
                                                        (df_unacc_minors['pregnant'] == 'yes')])
        else:
            unacc_pregnant_minors = 0

        # unaccompanied women
        df_women = df_adults[df_adults['gender'] == 'female']
        df_unacc_women = df_women[df_women['accompanied'] == 'no']
        unacc_women = len(df_unacc_women)
        if 'pregnant' in df_unacc_women.columns:
            unacc_pregnant_women = len(df_unacc_women[df_unacc_women['pregnant'] == 'yes'])
        else:
            unacc_pregnant_women = 0

    # disabled
    disabled = 0
    if 'disabled' in df_form.columns:
        disabled = len(df_form[df_form['disabled'] == 'yes'])

    # age groups
    age_group_counts = OrderedDict()
    if 'age' in df_form.columns:
        age_value_counts = df_form['age'].value_counts().to_dict()
        age_label_dict = {"u1": "Less than 1 year",
                          "1_4": "1-4 years",
                          "5_17": "5-17 years",
                          "18_50": "18-50 years",
                          "50p": "More than 50 years"}
        for age_label, age_text in age_label_dict.items():
            if age_label in age_value_counts.keys():
                age_group_counts[age_text] = age_value_counts[age_label]

    # nationalities
    country_counts = {}
    if 'country' in df_form.columns:
        country_counts = df_form['country'].value_counts().to_dict()
        country_counts = {k: v for k, v in sorted(country_counts.items(), key=lambda item: item[1], reverse=True)}

    return render_template('data.html',
                           total=total,
                           males=males,
                           females=females,
                           minors=minors,
                           minors_male=minors_male,
                           minors_female=minors_female,
                           pregnant=pregnant,
                           pregnant_women=pregnant_women,
                           pregnant_minors=pregnant_minors,
                           unacc_minors=unacc_minors,
                           unacc_minors_male=unacc_minors_male,
                           unacc_minors_female=unacc_minors_female,
                           unacc_pregnant_minors=unacc_pregnant_minors,
                           unacc_women=unacc_women,
                           unacc_pregnant_women=unacc_pregnant_women,
                           disabled=disabled,
                           age_value_counts=age_group_counts,
                           country_counts=country_counts,
                           rescues=rescues,
                           selected_rescue=str(rescue_number))


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
                                        'accompanied_by_who', 'pregnant', 'country'])
    return df_form


@app.route("/data", methods=['POST'])
def default_page():
    if request.form['password'] == os.getenv("PASSWORD"):
        df_form = get_data()
        return process_data(df_form)
    else:
        return render_template('home.html')


@app.route("/dataupdate", methods=['POST'])
def update_rescue():
    if 'rescue' in request.form.keys():
        rescue_number = request.form['rescue']
    else:
        rescue_number = None
    df_form = get_data()
    return process_data(df_form, rescue_number)


# def get_blob_service_client(blob_path):
#     blob_service_client = BlobServiceClient.from_connection_string(os.getenv("CONNECTION"))
#     return blob_service_client.get_blob_client(container='ocean-viking', blob=blob_path)


# def upload_data(data_path='rescue-data.xlsx', blob_path='website-data/rescue-data.xlsx'):
#     blob_client = get_blob_service_client(blob_path)
#     with open(data_path, "rb") as data:
#         blob_client.upload_blob(data, overwrite=True)


# @app.route("/download6", methods=['GET', 'POST'])
# def download_data(data_path='rescue-data-download.xlsx', blob_path='website-data/rescue-data.xlsx'):
#     if os.path.exists(data_path):
#         os.remove(data_path)
#     blob_client = get_blob_service_client(blob_path)
#     with open(data_path, "wb") as download_file:
#         download_file.write(blob_client.download_blob().readall())
#     return send_file('rescue-data-download.xlsx', as_attachment=True, attachment_filename="rescue-data.xlsx")


@app.route("/")
def login_page():
    return render_template('home.html')


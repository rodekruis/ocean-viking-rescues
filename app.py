import requests
import pandas as pd
from collections import OrderedDict
import smtplib, ssl, email
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import os
import pdfkit
from dotenv import load_dotenv
from azure.storage.blob import BlobServiceClient
from flask import Flask, render_template, request, send_file, make_response
from datetime import date
from googleapiclient.discovery import build
from google.oauth2 import service_account
app = Flask(__name__)
load_dotenv()  # take environment variables from .env


def process_data(df_form, rescue_number=None, return_data=False, report=False):

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

    columns_to_keep = ['rescue_number', 'age', 'gender', 'pregnant', 'accompanied', 'accompanied_by_who', 'country',
                       'bracelet_number', 'disabled', '_submission_time', 'rotation_no']
    for col in df_form.columns:
        if col not in columns_to_keep:
            df_form = df_form.drop(columns=[col])

    # check if there have been medevacs
    df_medevacs, rotation_no = get_data(os.getenv("ASSETMEDEVAC"))
    medevacs = 0
    if not df_medevacs.empty:
        medevacs = len(df_medevacs)
        for ix, row in df_medevacs.iterrows():
            if f'bracelet_evacuee' in row.keys():
                if not pd.isna(row['bracelet_evacuee']):
                    df_form = df_form[df_form['bracelet_number'] != row['bracelet_evacuee']]
            elif f'age_evacuee' in row.keys():
                if not pd.isna(row['age_evacuee']):
                    select = df_form[(df_form['age'] == row['age_evacuee']) & (df_form['gender'] == row['gender_evacuee'])].index
                    if len(select) > 0:
                        df_form = df_form.drop(select[0])
            for company_number in [1, 2, 3]:
                if f'bracelet_company_{company_number}' in df_medevacs.columns:
                    if not pd.isna(row[f'bracelet_company_{company_number}']):
                        medevacs += 1
                        df_form = df_form[df_form['bracelet_number'] != row[f'bracelet_company_{company_number}']]
                elif f'age_company_{company_number}' in df_medevacs.columns:
                    if not pd.isna(row[f'age_company_{company_number}']):
                        medevacs += 1
                        select = df_form[
                            (df_form['age'] == row[f'age_company_{company_number}']) & (df_form['gender'] == row[f'gender_company_{company_number}'])].index
                        if len(select) > 0:
                            df_form = df_form.drop(select[0])


    total = len(df_form)
    males, females, minors, minors_male, minors_female = 0, 0, 0, 0, 0
    pregnant, pregnant_women, pregnant_minors = 0, 0, 0
    unacc_minors, unacc_minors_male, unacc_minors_female, unacc_pregnant_minors = 0, 0, 0, 0
    unacc_women, unacc_pregnant_women = 0, 0
    disabled, disabled_male, disabled_female = 0, 0, 0
    age_group_counts = OrderedDict()
    uac_age_group_counts = OrderedDict()
    country_counts = {}

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
        if 'disabled' in df_form.columns:
            df_disabled = df_form[df_form['disabled'] == 'yes']
            disabled = len(df_disabled)
            disabled_male = len(df_disabled[df_disabled['gender'] == 'male'])
            disabled_female = len(df_disabled[df_disabled['gender'] == 'female'])

        # age groups
        if 'age' in df_form.columns:
            age_value_counts = df_form['age'].value_counts().to_dict()
            tot = sum(age_value_counts.values())
            age_label_dict = {"u1": "Less than 1 year",
                              "1_4": "1-4 years",
                              "5_17": "5-17 years",
                              "18_50": "18-50 years",
                              "50p": "More than 50 years"}
            for age_label, age_text in age_label_dict.items():
                if age_label in age_value_counts.keys():
                    age_group_counts[age_text] = [age_value_counts[age_label], 100.*age_value_counts[age_label]/tot]
            age_value_counts = df_unacc_minors['age'].value_counts().to_dict()
            tot = sum(age_value_counts.values())
            age_label_dict = {"u1": "Less than 1 year",
                              "1_4": "1-4 years",
                              "5_17": "5-17 years"}
            for age_label, age_text in age_label_dict.items():
                if age_label in age_value_counts.keys():
                    uac_age_group_counts[age_text] = [age_value_counts[age_label], 100. * age_value_counts[age_label] / tot]



        # nationalities
        if 'country' in df_form.columns:
            country_counts = df_form['country'].value_counts().to_dict()
            tot = sum(country_counts.values())
            country_counts = {k.replace('_', ' '): [v, 100.*v/tot] for k, v in sorted(country_counts.items(), key=lambda item: item[1], reverse=True)}

    if return_data:
        return df_form

    template = 'data.html' if not report else 'report.html'
    today = date.today()
    dt_ = today.strftime("%d-%m-%Y")

    return render_template(template,
                           rotation_no=rotation_no,
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
                           disabled_male=disabled_male,
                           disabled_female=disabled_female,
                           age_value_counts=age_group_counts,
                           uac_age_value_counts=uac_age_group_counts,
                           country_counts=country_counts,
                           rescues=rescues,
                           date=dt_,
                           medevacs=medevacs,
                           selected_rescue=str(rescue_number))


def get_data(asset):
    # get data from kobo
    headers = {'Authorization': f'Token {os.getenv("TOKEN")}'}
    data_request = requests.get(
        f'https://kobonew.ifrc.org/api/v2/assets/{asset}/data.json',
        headers=headers)
    data = data_request.json()

    # get rotation info
    SCOPES = ['https://www.googleapis.com/auth/spreadsheets.readonly']
    SAMPLE_SPREADSHEET_ID = '1L-d0lT2s7QjxlXbvYkcBWdSPFkKsYEtD52J_H4VK8dA'
    SAMPLE_RANGE_NAME = 'Rotations!A:C'
    sa_file = 'google-service-account-hspatsea-ocean-viking.json'
    creds = service_account.Credentials.from_service_account_file(sa_file, scopes=SCOPES)
    service = build('sheets', 'v4', credentials=creds)
    # Call the Sheets API
    sheet = service.spreadsheets()
    result = sheet.values().get(spreadsheetId=SAMPLE_SPREADSHEET_ID,
                                range=SAMPLE_RANGE_NAME).execute()
    values = result.get('values', [])
    df = pd.DataFrame.from_records(values[1:], columns=values[0])
    df['Start date'] = pd.to_datetime(df['Start date'], dayfirst=True)
    df['End date'] = pd.to_datetime(df['End date'], dayfirst=True)
    df['Rotation No'] = df['Rotation No'].astype(int)
    rotation_no = max(df['Rotation No'])
    start_date_ = date.today()
    end_date_ = date.today()

    if 'results' in data.keys():
        df_form = pd.DataFrame(data['results'])
        if df_form.empty:
            return df_form, rotation_no
        df_form['_submission_time'] = pd.to_datetime(df_form['_submission_time'])

        for ix, row in df.iterrows():
            if row['Start date'] <= pd.to_datetime(date.today()) <= row['End date']:
                rotation_no = row['Rotation No']
                start_date_ = row['Start date']
                end_date_ = row['End date']

        df_form = df_form[(df_form['_submission_time'] >= start_date_) & (df_form['_submission_time'] <= end_date_)]
        if not df_form.empty:
            df_form['rotation_no'] = rotation_no
        else:
            df_form = pd.DataFrame()
    else:
        df_form = pd.DataFrame()
    return df_form, rotation_no


def html_to_pdf(html, filename):
    try:
        pdfkit.from_string(html, filename)
    except:
        config = pdfkit.configuration(wkhtmltopdf=r'C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe')
        pdfkit.from_string(html, filename, configuration=config)


@app.route("/data", methods=['POST'])
def default_page():
    if request.form['password'] == os.getenv("PASSWORD"):
        df_form, rotation_no = get_data(os.getenv("ASSET"))
        return process_data(df_form)
    else:
        return render_template('home.html')


@app.route("/sendreport", methods=['POST'])
def send_report():
    if 'rescue' in request.form.keys():
        rescue_number = request.form['rescue']
        email = request.form['email']
    else:
        rescue_number = None

    today = date.today()
    d1 = today.strftime("%d-%m-%Y")
    filename = f"report--{d1}.html"

    df_form, rotation_no = get_data(os.getenv("ASSET"))
    report_html = process_data(df_form, rescue_number, report=True)
    # html_to_pdf(report_html, filename)
    with open(filename, "w") as file:
        file.write(report_html)

    port = 465  # For SSL
    smtp_server = "smtp.gmail.com"
    sender_email = "ocean.viking.rescues@gmail.com"  # Enter your address
    receiver_email = email  # Enter receiver address
    password = os.getenv("GOOGLEAPPPASS")

    # Create a multipart message and set headers
    message = MIMEMultipart()
    message["From"] = sender_email
    message["To"] = receiver_email
    message["Subject"] = "Ocean Viking Rescue Report"
    message["Bcc"] = receiver_email  # Recommended for mass emails
    rescue_number_text = "total rescued on board"
    if rescue_number != "total":
        rescue_number_text = f"rescue number {rescue_number}"
    body = f"""\
    Dear Sir/Madam,\n
    this is a message from the rescue vessel "Ocean Viking".\n
    Please find attached a report of the {rescue_number_text}."""
    message.attach(MIMEText(body, "plain"))

    with open(filename, "rb") as attachment:
        # Add file as application/octet-stream
        # Email client can usually download this automatically as attachment
        part = MIMEBase("application", "octet-stream")
        part.set_payload(attachment.read())
    # Encode file in ASCII characters to send by email
    encoders.encode_base64(part)
    # Add header as key/value pair to attachment part
    part.add_header(
        "Content-Disposition",
        f"attachment; filename= {filename}",
    )
    # Add attachment to message and convert message to string
    message.attach(part)

    context = ssl.create_default_context()
    with smtplib.SMTP_SSL(smtp_server, port, context=context) as server:
        server.login(sender_email, password)
        server.sendmail(sender_email, receiver_email, message.as_string())

    return process_data(df_form, rescue_number)


@app.route("/dataupdate", methods=['POST'])
def update_rescue():
    if 'rescue' in request.form.keys():
        rescue_number = request.form['rescue']
    else:
        rescue_number = None
    df_form, rotation_no = get_data(os.getenv("ASSET"))
    return process_data(df_form, rescue_number)


def get_blob_service_client(blob_path):
    blob_service_client = BlobServiceClient.from_connection_string(os.getenv("CONNECTION"))
    return blob_service_client.get_blob_client(container='ocean-viking', blob=blob_path)


def upload_data(data_path, blob_path):
    blob_client = get_blob_service_client(blob_path)
    with open(data_path, "rb") as data:
        blob_client.upload_blob(data, overwrite=True)


@app.route("/downloaddata", methods=['POST'])
def download_data():
    if 'rescue' in request.form.keys():
        rescue_number = request.form['rescue']
    else:
        rescue_number = None
    df_form, rotation_no = get_data(os.getenv("ASSET"))
    df_form = process_data(df_form, rescue_number, return_data=True)
    data_path = 'rescue_data.xlsx'
    if os.path.exists(data_path):
        os.remove(data_path)
    writer = pd.ExcelWriter('rescue_data.xlsx', engine='xlsxwriter')
    df_form.to_excel(writer, sheet_name='DATA', index=False)  # send df to writer
    worksheet = writer.sheets['DATA']  # pull worksheet object
    for idx, col in enumerate(df_form.columns):  # loop through all columns
        series = df_form[col]
        max_len = max((
            series.astype(str).map(len).max(),  # len of largest item
            len(str(series.name))  # len of column name/header
        )) + 1
        worksheet.set_column(idx, idx, max_len)  # set column width
    writer.save()
    return send_file(data_path, as_attachment=True, attachment_filename="rescue-data.xlsx")


@app.route("/")
def login_page():
    return render_template('home.html')


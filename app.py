import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import pandas as pd
from collections import OrderedDict
import os
import json
import numpy as np
from dotenv import load_dotenv
from azure.storage.blob import BlobServiceClient
from flask import Flask, render_template, request, send_file
from markupsafe import escape
from datetime import date
from googleapiclient.discovery import build
from google.oauth2 import service_account

app = Flask(__name__)
load_dotenv()  # take environment variables from .env


def get_blob_service_client(container, blob_path):
    blob_service_client = BlobServiceClient.from_connection_string(
        os.getenv("CONNECTION")
    )
    return blob_service_client.get_blob_client(container=container, blob=blob_path)


def upload_blob(container, blob_path, data_path):
    # upload data to azure blob storage
    blob_client = get_blob_service_client(container, blob_path)
    with open(data_path, "rb") as data:
        blob_client.upload_blob(data, overwrite=True)


def download_blob(container, blob_path, data_path):
    # download data from azure blob storage
    blob_client = get_blob_service_client(container, blob_path)
    with open(data_path, "wb") as download_file:
        download_file.write(blob_client.download_blob().readall())


def process_data(df_form, rescue_number=None, return_data=False, report=False):
    if "rescue_number" in df_form.columns:
        rescues = df_form["rescue_number"].unique().tolist()
    else:
        rescues = []
    if not rescues:
        rescues = [1]
    if not rescue_number:
        rescue_number = max(rescues)
    rescues = [str(x) for x in rescues]
    rescues = ["total"] + rescues
    if "rescue_number" in df_form.columns:
        if rescue_number != "total":
            df_form = df_form[df_form["rescue_number"] == rescue_number]
    else:
        df_form = pd.DataFrame()

    columns_to_keep = [
        "rescue_number",
        "age",
        "gender",
        "pregnant",
        "accompanied",
        "accompanied_by_who",
        "accompanied_by_who_adult",
        "country",
        "country_other",
        "bracelet_number",
        "disabled",
        "_submission_time",
        "rotation_no",
    ]
    for col in df_form.columns:
        if col not in columns_to_keep:
            df_form = df_form.drop(columns=[col])

    total_rescued, total_rescued_dict = len(df_form), {}
    if rescue_number == "total":
        if "rescue_number" in df_form.columns:
            for rn in df_form.rescue_number.unique():
                df_form_rn = df_form[df_form["rescue_number"] == rn]
                total_rescued_dict[rn] = len(df_form_rn)

    # check if there have been medevacs
    df_medevacs, rotation_no = get_data(os.getenv("ASSETMEDEVAC"))
    medevacs, medevacs_meta = 0, []
    try:
        df_medevacs = pd.merge(
            df_medevacs, df_form, left_on="bracelet_evacuee", right_on="bracelet_number"
        )
    except:
        pass
    if not df_medevacs.empty:
        medevacs = len(df_medevacs)
        for ix, row in df_medevacs.iterrows():
            medevacs_meta_no = 1
            if f"bracelet_evacuee" in row.keys():
                if not pd.isna(row["bracelet_evacuee"]):
                    df_form = df_form[
                        df_form["bracelet_number"] != row["bracelet_evacuee"]
                    ]
            elif f"age_evacuee" in row.keys():
                if not pd.isna(row["age_evacuee"]):
                    select = df_form[
                        (df_form["age"] == row["age_evacuee"])
                        & (df_form["gender"] == row["gender_evacuee"])
                    ].index
                    if len(select) > 0:
                        df_form = df_form.drop(select[0])
            if "_submission_time" in row.keys():
                medevacs_meta_date = pd.to_datetime(row["_submission_time"])
            else:
                medevacs_meta_date = "unknown"
            for company_number in [1, 2, 3]:
                if f"bracelet_company_{company_number}" in df_medevacs.columns:
                    if not pd.isna(row[f"bracelet_company_{company_number}"]):
                        medevacs += 1
                        medevacs_meta_no += 1
                        df_form = df_form[
                            df_form["bracelet_number"]
                            != row[f"bracelet_company_{company_number}"]
                        ]
                elif f"age_company_{company_number}" in df_medevacs.columns:
                    if not pd.isna(row[f"age_company_{company_number}"]):
                        medevacs += 1
                        medevacs_meta_no += 1
                        select = df_form[
                            (df_form["age"] == row[f"age_company_{company_number}"])
                            & (
                                df_form["gender"]
                                == row[f"gender_company_{company_number}"]
                            )
                        ].index
                        if len(select) > 0:
                            df_form = df_form.drop(select[0])
            medevacs_meta.append(
                {
                    "medevac_n": ix,
                    "medevac_n_evacuees": medevacs_meta_no,
                    "medevac_date": medevacs_meta_date,
                }
            )

    # check if there have been disembarkations
    df_disembark, rotation_no = get_data(os.getenv("ASSETDISEMBARK"))
    for ix, row in df_disembark.iterrows():
        if row["type"] == "rescue":
            rescue_no = row["rescue_number"].split(" ")
            df_form = df_form[~df_form["rescue_number"].isin(rescue_no)]
        elif row["type"] == "bracelet":
            if row["bracelet_range_or_numbers"] == "range":
                df_form["bracelet_number_int"] = (
                    df_form["bracelet_number"].fillna(0).astype(int)
                )
                df_form = df_form[
                    ~df_form["bracelet_number_int"].between(
                        int(row["range_start"]), int(row["range_end"]), inclusive="both"
                    )
                ]
                df_form = df_form.drop(columns=["bracelet_number_int"])
            elif row["bracelet_range_or_numbers"] == "numbers":
                df_form = df_form[
                    ~df_form["bracelet_number"].isin(row["numbers"].split(", "))
                ]

    # calculate total
    total, total_dict = len(df_form), {}
    if rescue_number == "total":
        if "rescue_number" in df_form.columns:
            for rn in df_form.rescue_number.unique():
                df_form_rn = df_form[df_form["rescue_number"] == rn]
                total_dict[rn] = len(df_form_rn)

    # calculate all the rest
    males, females, minors, minors_male, minors_female = 0, 0, 0, 0, 0
    pregnant, pregnant_women, pregnant_minors = 0, 0, 0
    unacc_minors, unacc_minors_male, unacc_minors_female, unacc_pregnant_minors = (
        0,
        0,
        0,
        0,
    )
    unacc_women, unacc_pregnant_women = 0, 0
    single_or_pregnant_women = 0
    disabled, disabled_male, disabled_female = 0, 0, 0
    age_group_counts = OrderedDict()
    uac_age_group_counts = OrderedDict()
    country_counts = {}

    if "gender" in df_form.columns:
        males = len(df_form[df_form["gender"] == "male"])
        females = len(df_form[df_form["gender"] == "female"])
        df_minors = df_form[(df_form["age"] != "18_50") & (df_form["age"] != "50p")]
        df_adults = df_form[(df_form["age"] == "18_50") | (df_form["age"] == "50p")]

        # minors
        minors = len(df_minors)
        minors_male = len(df_minors[df_minors["gender"] == "male"])
        minors_female = len(df_minors[df_minors["gender"] == "female"])

        # unaccompanied minors
        df_unacc_minors = df_minors[df_minors["accompanied"] == "no"]
        if (
            "accompanied_by_who" in df_minors.columns
            and "accompanied_by_who_adult" in df_minors.columns
        ):
            df_unacc_minors = pd.concat(
                [
                    df_unacc_minors,
                    df_minors[
                        (df_minors["accompanied"] == "yes")
                        & (df_minors["accompanied_by_who_adult"] == "no")
                    ],
                ]
            )
        unacc_minors = len(df_unacc_minors)
        unacc_minors_male = len(df_unacc_minors[df_unacc_minors["gender"] == "male"])
        unacc_minors_female = len(
            df_unacc_minors[df_unacc_minors["gender"] == "female"]
        )

        # unaccompanied pregnant minors
        if "pregnant" in df_unacc_minors.columns:
            unacc_pregnant_minors = len(
                df_unacc_minors[
                    (df_unacc_minors["gender"] == "female")
                    & (df_unacc_minors["pregnant"] == "yes")
                ]
            )
        else:
            unacc_pregnant_minors = 0

        # pregnant women
        if "pregnant" in df_form.columns:
            pregnant = len(df_form[df_form["pregnant"] == "yes"])
        if "pregnant" in df_adults.columns:
            pregnant_women = len(df_adults[df_adults["pregnant"] == "yes"])
        if "pregnant" in df_minors.columns:
            pregnant_minors = len(df_minors[df_minors["pregnant"] == "yes"])

        # unaccompanied women
        df_women = df_adults[df_adults["gender"] == "female"]
        df_women.to_excel("women.xlsx", index=False)
        df_unacc_women = df_women[df_women["accompanied"] == "no"]
        df_unacc_women = pd.concat(
            [
                df_unacc_women,
                df_women[
                    (df_women["accompanied"] == "yes")
                    & (df_women["accompanied_by_who"] == "child")
                ],
            ]
        )
        unacc_women = len(df_unacc_women)
        if "pregnant" in df_unacc_women.columns:
            unacc_pregnant_women = len(
                df_unacc_women[df_unacc_women["pregnant"] == "yes"]
            )
        else:
            unacc_pregnant_women = 0

        # total single or pregnant
        if (
            "pregnant" in df_form.columns
            and "gender" in df_form.columns
            and "accompanied" in df_form.columns
            and "accompanied_by_who" in df_form.columns
            and "accompanied_by_who_adult" in df_form.columns
        ):
            single_or_pregnant_women = len(
                df_form[
                    (df_form["pregnant"] == "yes")
                    | (
                        (df_form["gender"] == "female")
                        & (df_form["accompanied"] == "no")
                    )
                    | (
                        (df_form["gender"] == "female")
                        & (df_form["accompanied"] == "yes")
                        & (df_form["accompanied_by_who"] == "child")
                    )
                    | (
                        (df_form["age"] != "18_50")
                        & (df_form["age"] != "50p")
                        & (df_form["gender"] == "female")
                        & (df_form["accompanied"] == "yes")
                        & (df_minors["accompanied_by_who_adult"] == "no")
                    )
                ]
            )

        # disabled
        if "disabled" in df_form.columns:
            df_disabled = df_form[df_form["disabled"] == "yes"]
            disabled = len(df_disabled)
            disabled_male = len(df_disabled[df_disabled["gender"] == "male"])
            disabled_female = len(df_disabled[df_disabled["gender"] == "female"])

        # age groups
        if "age" in df_form.columns:
            age_value_counts = df_form["age"].value_counts().to_dict()
            tot = sum(age_value_counts.values())
            age_label_dict = {
                "u1": "Less than 1 year",
                "1_4": "1-4 years",
                "5_13": "5-13 years",
                "5_17": "5-17 years",
                "14_17": "14-17 years",
                "18_50": "18-50 years",
                "50p": "More than 50 years",
            }
            for age_label, age_text in age_label_dict.items():
                if age_label in age_value_counts.keys():
                    age_group_counts[age_text] = [
                        age_value_counts[age_label],
                        100.0 * age_value_counts[age_label] / tot,
                    ]
            age_value_counts = df_unacc_minors["age"].value_counts().to_dict()
            tot = sum(age_value_counts.values())
            age_label_dict = {
                "u1": "Less than 1 year",
                "1_4": "1-4 years",
                "5_13": "5-13 years",
                "5_17": "5-17 years",
                "14_17": "14-17 years",
            }
            for age_label, age_text in age_label_dict.items():
                if age_label in age_value_counts.keys():
                    uac_age_group_counts[age_text] = [
                        age_value_counts[age_label],
                        100.0 * age_value_counts[age_label] / tot,
                    ]

        # nationalities
        if "country_other" in df_form.columns:
            df_form["country"] = np.where(
                df_form["country"] == "other",
                df_form["country_other"].str.lower(),
                df_form["country"],
            )
            df_form = df_form.drop(columns=["country_other"])

        if "country" in df_form.columns:
            country_counts = df_form["country"].value_counts().to_dict()
            tot = sum(country_counts.values())
            country_counts = {
                k.replace("_", " "): [v, 100.0 * v / tot]
                for k, v in sorted(
                    country_counts.items(), key=lambda item: item[1], reverse=True
                )
            }

    if return_data:
        return df_form

    template = "data.html"
    dt_ = date.today().strftime("%d-%m-%Y")

    report_dict = {
        "rotation_no": rotation_no,
        "total_rescued": total_rescued,
        "total_rescued_dict": total_rescued_dict,
        "total": total,
        "total_dict": total_dict,
        "males": males,
        "females": females,
        "minors": minors,
        "minors_male": minors_male,
        "minors_female": minors_female,
        "pregnant": pregnant,
        "pregnant_women": pregnant_women,
        "pregnant_minors": pregnant_minors,
        "unacc_minors": unacc_minors,
        "unacc_minors_male": unacc_minors_male,
        "unacc_minors_female": unacc_minors_female,
        "unacc_pregnant_minors": unacc_pregnant_minors,
        "unacc_women": unacc_women,
        "unacc_pregnant_women": unacc_pregnant_women,
        "disabled": disabled,
        "disabled_male": disabled_male,
        "disabled_female": disabled_female,
        "age_value_counts": age_group_counts,
        "uac_age_value_counts": uac_age_group_counts,
        "country_counts": country_counts,
        "rescues": rescues,
        "date": dt_,
        "medevacs": medevacs,
        "medevacs_meta": medevacs_meta,
        "selected_rescue": escape(str(rescue_number)),
    }

    template = render_template(
        template,
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
        single_or_pregnant_women=single_or_pregnant_women,
        disabled=disabled,
        disabled_male=disabled_male,
        disabled_female=disabled_female,
        age_value_counts=age_group_counts,
        uac_age_value_counts=uac_age_group_counts,
        country_counts=country_counts,
        rescues=rescues,
        date=dt_,
        medevacs=medevacs,
        selected_rescue=str(rescue_number),
    )

    if report:
        return template, report_dict
    else:
        return template


def get_data(asset):
    # get data from kobo
    headers = {"Authorization": f'Token {os.getenv("TOKEN")}'}
    session = requests.Session()
    retry = Retry(connect=10, backoff_factor=0.5)
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    data_request = session.get(
        f"https://kobo.ifrc.org/api/v2/assets/{asset}/data.json", headers=headers
    )
    data = data_request.json()

    # get rotation info
    SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]
    SAMPLE_SPREADSHEET_ID = os.getenv("GOOGLESHEETID")
    SAMPLE_RANGE_NAME = "Rotations!A:C"
    sa_file = json.loads(os.getenv("GOOGLESERVICEACCUNT"))
    creds = service_account.Credentials.from_service_account_info(
        sa_file, scopes=SCOPES
    )
    service = build("sheets", "v4", credentials=creds)
    # Call the Sheets API
    sheet = service.spreadsheets()
    result = (
        sheet.values()
        .get(spreadsheetId=SAMPLE_SPREADSHEET_ID, range=SAMPLE_RANGE_NAME)
        .execute()
    )
    values = result.get("values", [])
    df = pd.DataFrame.from_records(values[1:], columns=values[0])
    df["Start date"] = pd.to_datetime(df["Start date"], dayfirst=True)
    df["End date"] = pd.to_datetime(df["End date"], dayfirst=True)
    df["Rotation No"] = df["Rotation No"].astype(float)
    rotation_no = max(df["Rotation No"])
    start_date_ = pd.to_datetime(date.today(), utc=True)
    end_date_ = pd.to_datetime(date.today(), utc=True)

    if "results" in data.keys():
        df_form = pd.DataFrame(data["results"])
        if df_form.empty:
            return df_form, rotation_no

        for ix, row in df.iterrows():
            if row["Start date"] <= pd.to_datetime(date.today()) <= row["End date"]:
                rotation_no = row["Rotation No"]
                start_date_ = pd.to_datetime(row["Start date"], utc=True)
                end_date_ = pd.to_datetime(row["End date"], utc=True)

        df_form["start"] = pd.to_datetime(df_form["start"], utc=True)
        df_form = df_form[
            (df_form["start"] >= start_date_) & (df_form["start"] <= end_date_)
        ]
        if not df_form.empty:
            df_form["rotation_no"] = rotation_no
        else:
            df_form = pd.DataFrame()

        # Get rescue number if more than 7 rescues
        if "specify_rescue_number" in df_form.columns:
            df_form["rescue_number"] = np.where(
                df_form["rescue_number"] == ">7",
                df_form["specify_rescue_number"],
                df_form["rescue_number"],
            )
    else:
        df_form = pd.DataFrame()
    return df_form, rotation_no


@app.route("/data", methods=["POST"])
def default_page():
    if request.form["password"] == os.getenv("PASSWORD"):
        df_form, rotation_no = get_data(os.getenv("ASSET"))
        return process_data(df_form)
    else:
        return render_template("home.html")


@app.route("/sendreport", methods=["POST"])
def send_report():
    if "rescue" in request.form.keys():
        rescue_number = request.form["rescue"]
        email = request.form["email"]
    else:
        rescue_number = None
        email = ""

    dataname = "report_data"
    df_form, rotation_no = get_data(os.getenv("ASSET"))
    if "rescue_number" in df_form.columns:
        rescues = df_form["rescue_number"].unique().tolist()
    else:
        rescues = []
    df_rescue_dates = df_form.groupby("rescue_number")["_submission_time"].min()
    report_template, report_data = process_data(df_form, rescue_number, report=True)

    filename = dataname + "_general.csv"
    df_metadata = pd.DataFrame()
    if rescue_number == "total":
        for norescue, rescue in enumerate(rescues):
            if rescue in report_data["total_dict"].keys():
                df_metadata.at[norescue, "email"] = email
                df_metadata.at[norescue, "rescue_number"] = rescue
                df_metadata.at[norescue, "people_rescued"] = report_data[
                    "total_rescued_dict"
                ][rescue]
                df_metadata.at[norescue, "people_onboard"] = report_data["total_dict"][
                    rescue
                ]
                df_metadata.at[norescue, "date"] = df_rescue_dates.loc[rescue]
                df_metadata.at[norescue, "medevac"] = report_data["medevacs"]
    else:
        df_metadata.at[rescue_number, "email"] = email
        df_metadata.at[rescue_number, "rescue_number"] = rescue_number
        df_metadata.at[rescue_number, "people_rescued"] = report_data["total_rescued"]
        df_metadata.at[rescue_number, "people_onboard"] = report_data["total"]
        df_metadata.at[rescue_number, "date"] = df_rescue_dates.loc[rescue_number]
        df_metadata.at[rescue_number, "medevac"] = report_data["medevacs"]
    df_metadata.to_csv(filename)
    upload_blob("reporting", filename, filename)

    filename = dataname + "_medevacs.csv"
    df_medevac = pd.DataFrame()
    for medevac_meta in report_data["medevacs_meta"]:
        df_medevac.at[medevac_meta["medevac_n"], "medevac_n"] = medevac_meta[
            "medevac_n"
        ]
        df_medevac.at[medevac_meta["medevac_n"], "medevac_n_evacuees"] = medevac_meta[
            "medevac_n_evacuees"
        ]
        df_medevac.at[medevac_meta["medevac_n"], "medevac_date"] = medevac_meta[
            "medevac_date"
        ]
    df_medevac.to_csv(filename)
    upload_blob("reporting", filename, filename)

    filename = dataname + "_peopleonboard.csv"
    df_peopleonboard = pd.DataFrame()
    df_peopleonboard.at["Adults", "Males"] = (
        report_data["males"] - report_data["minors_male"]
    )
    df_peopleonboard.at["Adults", "Females"] = (
        report_data["females"] - report_data["minors_female"]
    )
    df_peopleonboard.at["Adults", "Total"] = (
        report_data["total"] - report_data["minors"]
    )
    df_peopleonboard.at["Adults", "Percentage"] = (
        report_data["total"] - report_data["minors"]
    ) / report_data["total"]
    df_peopleonboard.at["Accompanied minors", "Males"] = (
        report_data["minors_male"] - report_data["unacc_minors_male"]
    )
    df_peopleonboard.at["Accompanied minors", "Females"] = (
        report_data["minors_female"] - report_data["unacc_minors_female"]
    )
    df_peopleonboard.at["Accompanied minors", "Total"] = (
        report_data["minors"] - report_data["unacc_minors"]
    )
    df_peopleonboard.at["Accompanied minors", "Percentage"] = (
        report_data["minors"] - report_data["unacc_minors"]
    ) / report_data["total"]
    df_peopleonboard.at["Unaccompanied minors", "Males"] = report_data[
        "unacc_minors_male"
    ]
    df_peopleonboard.at["Unaccompanied minors", "Females"] = report_data[
        "unacc_minors_female"
    ]
    df_peopleonboard.at["Unaccompanied minors", "Total"] = report_data["unacc_minors"]
    df_peopleonboard.at["Unaccompanied minors", "Percentage"] = (
        report_data["unacc_minors"] / report_data["total"]
    )
    df_peopleonboard.at["TOTAL", "Males"] = report_data["males"]
    df_peopleonboard.at["TOTAL", "Females"] = report_data["females"]
    df_peopleonboard.at["TOTAL", "Total"] = report_data["total"]
    df_peopleonboard.to_csv(filename)
    upload_blob("reporting", filename, filename)

    filename = dataname + "_nationalities.csv"
    df_nationalities = pd.DataFrame()
    df_nationalities.drop(df_nationalities.index, inplace=True)
    for nationality, count in report_data["country_counts"].items():
        df_nationalities.at[nationality.title(), "Total"] = count[0]
        df_nationalities.at[nationality.title(), "Percentage"] = count[1] / 100.0
    df_nationalities.to_csv(filename)
    upload_blob("reporting", filename, filename)

    filename = dataname + "_age.csv"
    df_age = pd.DataFrame()
    df_age.drop(df_age.index, inplace=True)
    for age_group, age_count in report_data["age_value_counts"].items():
        df_age.at[age_group, "Total"] = age_count[0]
        df_age.at[age_group, "Percentage"] = age_count[1] / 100.0
    df_age.to_csv(filename)
    upload_blob("reporting", filename, filename)

    filename = dataname + "_disabilities.csv"
    df_disabilities = pd.DataFrame()
    df_disabilities.at["all", "Males"] = report_data["disabled_male"]
    df_disabilities.at["all", "Females"] = report_data["disabled_female"]
    df_disabilities.at["all", "Total"] = report_data["disabled"]
    df_disabilities.to_csv(filename)
    upload_blob("reporting", filename, filename)

    filename = dataname + "_pregnant.csv"
    df_pregnant = pd.DataFrame()
    df_pregnant.at["Pregnant", "Adults"] = report_data["pregnant_women"]
    df_pregnant.at["Pregnant", "Minors"] = report_data["pregnant_minors"]
    df_pregnant.at["Pregnant", "Total"] = report_data["pregnant"]
    df_pregnant.at["Single females", "Adults"] = report_data["unacc_women"]
    df_pregnant.at["Single females", "Minors"] = report_data["unacc_minors_female"]
    df_pregnant.at["Single females", "Total"] = (
        report_data["unacc_women"] + report_data["unacc_minors_female"]
    )
    df_pregnant.at["TOTAL", "Adults"] = (
        report_data["pregnant_women"] + report_data["unacc_women"]
    )
    df_pregnant.at["TOTAL", "Minors"] = (
        report_data["pregnant_minors"] + report_data["unacc_minors_female"]
    )
    df_pregnant.at["TOTAL", "Total"] = (
        report_data["pregnant"]
        + report_data["unacc_women"]
        + report_data["unacc_minors_female"]
    )
    df_pregnant.to_csv(filename)
    upload_blob("reporting", filename, filename)

    requests.post(
        url=os.getenv("LOGICAPPTRIGGER"),
        json={"email": email},
        headers={"Content-type": "application/json"},
    )

    return report_template


@app.route("/dataupdate", methods=["POST"])
def update_rescue():
    if "rescue" in request.form.keys():
        rescue_number = request.form["rescue"]
    else:
        rescue_number = None
    df_form, rotation_no = get_data(os.getenv("ASSET"))
    return process_data(df_form, rescue_number)


@app.route("/downloaddata", methods=["POST"])
def download_data():
    if "rescue" in request.form.keys():
        rescue_number = request.form["rescue"]
    else:
        rescue_number = None
    df_form, rotation_no = get_data(os.getenv("ASSET"))
    df_form = process_data(df_form, rescue_number, return_data=True)
    data_path = "rescue_data.xlsx"
    if os.path.exists(data_path):
        os.remove(data_path)
    writer = pd.ExcelWriter("rescue_data.xlsx", engine="xlsxwriter")
    df_form.to_excel(writer, sheet_name="DATA", index=False)  # send df to writer
    worksheet = writer.sheets["DATA"]  # pull worksheet object
    for idx, col in enumerate(df_form.columns):  # loop through all columns
        series = df_form[col]
        max_len = (
            max(
                (
                    series.astype(str).map(len).max(),  # len of largest item
                    len(str(series.name)),  # len of column name/header
                )
            )
            + 1
        )
        worksheet.set_column(idx, idx, max_len)  # set column width
    writer._save()
    return send_file(data_path, as_attachment=True, download_name="rescue-data.xlsx")


@app.route("/vessellocations")
def vessel_locations():
    return render_template("vessellocations.html")


@app.route("/")
def login_page():
    return render_template("home.html")

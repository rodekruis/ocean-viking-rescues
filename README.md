# ocean-viking-rescues

Developed for the [rescue ship "Ocean Viking"](https://sosmediterranee.com/about-us/) in support of the [HSP@Sea operation](https://go.ifrc.org/emergencies/5425).

## Description

Synopsis: a [flask python app](https://flask.palletsprojects.com/en/2.0.x/) that is connected to [Kobo](https://www.kobotoolbox.org/) (data collection tool).

Worflow: a kobo form registers rescuees. From a website, the team can retrieve each rescuee's information, as well as having an overview of all rescuees. Reports can be automatically generated and sent via email.

## Setup

1. [Create an account on Kobo](https://kf.kobotoolbox.org/accounts/register/#/)
2. Set up the form in Kobo, [here](https://github.com/rodekruis/ocean-viking-medical/blob/main/kobo-forms/medical-form.xlsx) is the template.
3. Create a .env file in the root directory and add the following credentials
   * TOKEN: KoBo API user token
   * ASSET: ID of the form
   * PASSWORD: to login into the website
5. Deploy the flask application [using Azure Web App](https://docs.microsoft.com/en-us/azure/app-service/quickstart-python?tabs=bash&pivots=python-framework-flask)

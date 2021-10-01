import streamlit as st
import json
import datetime
from supabase_py import create_client, Client

st.set_page_config(page_title='Liquidationsrechner', page_icon=":ledger:",)

st.title('Inoffizieller Liquidationsrechner Kanton St. Gallen')

f_municipalities = open('municipalities.json')
municipalities = json.load(f_municipalities)
f_municipalities.close()
CURRENT_YEAR = datetime.datetime.now().year
NOTIONAL_PURCHASE_RATE = 0.022
NOTIONAL_PURCHASE_RATE_MARRIED = 0.02
OTHER_LIQUIDATION_RATE = 0.04
APIKEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJyb2xlIjoiYW5vbiIsImlhdCI6MTYzMjYwNDgyMSwiZXhwIjoxOTQ4MTgwODIxfQ.lGyzXxNAeor9HBd2wcaJ4he1SxMBXEM13PbLmYsxjcM'
URL = 'https://hbhuxcikiovvpeiwgnqf.supabase.co'

supabase: Client = create_client(URL, APIKEY)

def calculate_simple_tax(married, notional_purchase, other_liquidation_profit):
    notional_purchase_tax = 0
    if married:
        notional_purchase_tax += notional_purchase * NOTIONAL_PURCHASE_RATE_MARRIED
    else:
        notional_purchase_tax += notional_purchase * NOTIONAL_PURCHASE_RATE
    
    other_liquidation_profit_tax = other_liquidation_profit * OTHER_LIQUIDATION_RATE
    return other_liquidation_profit_tax + notional_purchase_tax

def find_municipality_data(data, municipality):
    for tax_rate in data['data']:
        if tax_rate['Commune Name'] == municipality:
            return tax_rate

def extract_simple_tax_multiplier(municipality_data, married, denomination, denomination_partner):
    simple_tax_multiplier = municipality_data['Canton Rate']
    simple_tax_multiplier += municipality_data['Commune Rate']
    target_data_denomination = transform_input_denomination_to_target_data_denomination(denomination)
    target_data_denomination_partner = transform_input_denomination_to_target_data_denomination(denomination_partner)
    # Denomination tax rate of married couple has to be added and then substracted by 2
    if not married:
        simple_tax_multiplier += municipality_data.get(target_data_denomination,0)
    else:
        simple_tax_multiplier += (municipality_data.get(target_data_denomination,0) + municipality_data.get(target_data_denomination_partner,0))/2
            
    return simple_tax_multiplier/100

def calculate_federal_tax(tax_amount, married):
    federal_data = supabase.table("Federal Tax Rate").select("*").eq('Married', str(married)).execute()
    federal_tax_rates = federal_data['data']
    target_federal_tax_rate = federal_tax_rates[0]
    for i in range(len(federal_tax_rates)):
        if i == (len(federal_tax_rates)-1):
            target_federal_tax_rate = federal_tax_rates[i-1]
        if tax_amount < federal_tax_rates[i]["Income"]:
            if i != 0:
                target_federal_tax_rate = federal_tax_rates[i-1]
            break
    return target_federal_tax_rate["Tax"] + (int((tax_amount - target_federal_tax_rate["Income"])/100) * target_federal_tax_rate["Progression"])

def transform_input_denomination_to_target_data_denomination(input_denomination):
    if input_denomination == 'Evangelisch':
        return 'Church, Protestant'
    elif input_denomination == 'Römisch-Katholisch':
        return 'Church, Roman Catholic'
    else:
        return ''

def validate_input():
    if st.session_state.married == False and st.session_state.denomination_partner != 'Konfessionslos':
        st.session_state.denomination_partner = 'Konfessionslos'
        st.info('Die Konfession Ehepartner wurde auf konfessionslos gestellt, da verheiratet nicht ausgewählt wurde')

with st.form(key='liquidation_information'):
    year_input = st.number_input('Steuerjahr', min_value=2019, max_value=2021, value=CURRENT_YEAR-1, step=1)
    municipality = st.selectbox('Gemeinde', municipalities)
    married = st.checkbox('Verheiratet', key='married')
    denomination = st.selectbox('Konfession', ('Konfessionslos', 'Römisch-Katholisch', 'Evangelisch'), key='denomination')
    denomination_partner = st.selectbox('Konfession Ehepartner', ('Konfessionslos', 'Römisch-Katholisch', 'Evangelisch'), key='denomination_partner')
    notional_purchase = st.number_input('Fiktiver Einkauf', step=1, key='notional_purchase')
    other_liquidation_profit = st.number_input('Übriger Liquidationsgewinn', step=1, key='other_liquidation_profit')
    submit_button = st.form_submit_button(label='Berechnen', on_click=validate_input)

if submit_button:
    data = supabase.table("Swiss Tax Rate").select("*").eq('Canton', 'SG').eq('Tax Year', str(year_input)).execute()
    simple_tax = calculate_simple_tax(married, notional_purchase, other_liquidation_profit)
    municipality_data = find_municipality_data(data, municipality)
    simple_tax_multiplier = extract_simple_tax_multiplier(municipality_data, married, denomination, denomination_partner)
    local_tax = simple_tax * simple_tax_multiplier

    federal_tax_other_liquidation_profit = calculate_federal_tax(other_liquidation_profit/5, married)
    # Ensure 0 input does not result in division by 0
    if other_liquidation_profit == 0:
        other_liquidation_profit_divider = 1
    else:
        other_liquidation_profit_divider = other_liquidation_profit
    
    federal_tax_other_liquidation_profit_rate = federal_tax_other_liquidation_profit / (other_liquidation_profit_divider/5)

    if federal_tax_other_liquidation_profit_rate < 0.02:
        federal_tax_other_liquidation_profit_rate = 0.02

    federal_tax_other_liquidation_profit = other_liquidation_profit * federal_tax_other_liquidation_profit_rate
    federal_tax_notional_purchase = calculate_federal_tax(notional_purchase, married)/5
    federal_tax = federal_tax_notional_purchase + federal_tax_other_liquidation_profit

    col1, col2 = st.columns(2)
    col1.metric(label='Kantons- und Gemeindesteuern', value="CHF {:,.2f}".format(local_tax))
    col2.metric(label='Bundessteuern', value="CHF {:,.2f}".format(federal_tax))
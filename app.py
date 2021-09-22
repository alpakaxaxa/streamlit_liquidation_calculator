import streamlit as st
import json
import datetime

st.set_page_config(page_title='Liquidationsrechner', page_icon=":ledger:",)

st.title('Inoffizieller Liquidationsrechner Kanton St. Gallen')

f_municipalities = open('municipalities.json')
municipalities = json.load(f_municipalities)
f_municipalities.close()
CURRENT_YEAR = datetime.datetime.now().year
NOTIONAL_PURCHASE_RATE = 0.022
NOTIONAL_PURCHASE_RATE_MARRIED = 0.02
OTHER_LIQUIDATION_RATE = 0.04

def calculate_simple_tax(married, notional_purchase, other_liquidation_profit):
    notional_purchase_tax = 0
    if married:
        notional_purchase_tax += notional_purchase * NOTIONAL_PURCHASE_RATE_MARRIED
    else:
        notional_purchase_tax += notional_purchase * NOTIONAL_PURCHASE_RATE
    
    other_liquidation_profit_tax = other_liquidation_profit * OTHER_LIQUIDATION_RATE
    return other_liquidation_profit_tax + notional_purchase_tax

def find_municipality_data(tax_year, municipality):
    f_tax_rates = open('data.json')
    tax_rates_all_periods = json.load(f_tax_rates)
    tax_rates = tax_rates_all_periods[str(tax_year)]
    for tax_rate in tax_rates:
        if tax_rate['Commune'] == municipality:
            return tax_rate

def extract_simple_tax_multiplier(municipality_data, denomination, denomination_partner):
    simple_tax_multiplier = municipality_data['Canton_1']
    simple_tax_multiplier += municipality_data['Commune_1']
    target_data_denomination = transform_input_denomination_to_target_data_denomination(denomination)
    if target_data_denomination != '':
        simple_tax_multiplier += municipality_data[target_data_denomination]
    target_data_denomination_partner = transform_input_denomination_to_target_data_denomination(denomination_partner)
    if target_data_denomination_partner != '':
        simple_tax_multiplier += municipality_data[target_data_denomination_partner]

    return simple_tax_multiplier/100

def calculate_federal_tax(file_name, tax_amount, federal_tax_multiplier=1):
    f_federal_tax = open(file_name)
    federal_tax_rates = json.load(f_federal_tax)
    f_federal_tax.close()

    target_federal_tax_rate = None
    for i, tax_rate in enumerate(federal_tax_rates):
        if tax_amount < tax_rate["income"]:
            target_federal_tax_rate = federal_tax_rates[i-1]
            break
        else:
            continue
    
    if target_federal_tax_rate != None:
        federal_tax = target_federal_tax_rate["tax"] + (int((tax_amount - target_federal_tax_rate["income"])/100) * target_federal_tax_rate["progression"])
        return federal_tax
    return 0            

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
    year_input = st.number_input('Steuerjahr', min_value=2020, max_value=2020, value=CURRENT_YEAR-1, step=1)
    municipality = st.selectbox('Gemeinde', municipalities)
    married = st.checkbox('Verheiratet', key='married')
    denomination = st.selectbox('Konfession', ('Konfessionslos', 'Römisch-Katholisch', 'Evangelisch'), key='denomination')
    denomination_partner = st.selectbox('Konfession Ehepartner', ('Konfessionslos', 'Römisch-Katholisch', 'Evangelisch'), key='denomination_partner')
    notional_purchase = st.number_input('Fiktiver Einkauf', step=1, key='notional_purchase')
    other_liquidation_profit = st.number_input('Übriger Liquidationsgewinn', step=1, key='other_liquidation_profit')
    submit_button = st.form_submit_button(label='Berechnen', on_click=validate_input)

if submit_button:
    simple_tax = calculate_simple_tax(married, notional_purchase, other_liquidation_profit)
    municipality_data = find_municipality_data(year_input, municipality)
    simple_tax_multiplier = extract_simple_tax_multiplier(municipality_data, denomination, denomination_partner)
    local_tax = simple_tax * simple_tax_multiplier

    if married == False:
        federal_tax_notional_purchase = calculate_federal_tax('federal_tax.json', notional_purchase)/5
        federal_tax_other_liquidation_profit = calculate_federal_tax('federal_tax.json', other_liquidation_profit/5)
    else:
        federal_tax_notional_purchase = calculate_federal_tax('federal_tax_married.json', notional_purchase)/5
        federal_tax_other_liquidation_profit = calculate_federal_tax('federal_tax_married.json', other_liquidation_profit/5)

    # Ensure that user input of 0 does not produce divison by 0
    other_liquidation_profit_divider = 0
    if other_liquidation_profit == 0:
        other_liquidation_profit_divider = 1
    else:
        other_liquidation_profit_divider = other_liquidation_profit

    if federal_tax_other_liquidation_profit / other_liquidation_profit_divider < 0.02:
        federal_tax_other_liquidation_profit = other_liquidation_profit * 0.02
    
    federal_tax = federal_tax_notional_purchase + federal_tax_other_liquidation_profit

    print('Simple Tax', simple_tax)
    print('Local Tax: ', local_tax)
    print('Federal Tax: ', federal_tax)
    print('Multiplier: ', simple_tax_multiplier)

    col1, col2 = st.columns(2)
    col1.metric(label='Kantons- und Gemeindesteuern', value="CHF {:,.2f}".format(local_tax))
    col2.metric(label='Bundessteuern', value="CHF {:,.2f}".format(federal_tax))


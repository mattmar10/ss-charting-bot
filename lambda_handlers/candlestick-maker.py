
import boto3
import matplotlib.pyplot as plt
import os
import requests
import pandas as pd
import mplfinance as mpf
import json
from io import BytesIO
import uuid
import matplotlib
import datetime
matplotlib.use('Agg')


base_url = 'https://financialmodelingprep.com/api/v3'
api_key = os.environ.get('FMP_API_KEY')
bucket_name = os.environ.get('CHART_BUCKET')
s3 = boto3.client('s3')


def make_candlestick_chart(ticker, include_volume=False):
    print('fetching candles')
    data = fetch_data_from_api(ticker)
    spy_data = fetch_data_from_api('SPY')
    print('fetching candles complete')

    if data:
        print('prepping plot')
        ohlc_data = [(row['date'], row['open'], row['high'],
                      row['low'], row['close']) for row in data['historical']]
        volume_data = [row['volume'] for row in data['historical']]

        spy_ohlc_data = [(row['date'], row['close'])
                         for row in spy_data['historical']]

        ohlc_data_reversed = ohlc_data[::-1]
        volume_data_reversed = volume_data[::-1]

        # Create a DataFrame from the OHLC and volume data
        df = pd.DataFrame(ohlc_data_reversed, columns=[
                          'Date', 'Open', 'High', 'Low', 'Close'])

        # Convert date column to datetime format
        df['Date'] = pd.to_datetime(df['Date'], format='%Y-%m-%d')
        df.set_index('Date', inplace=True)  # Set Date column as index
        # Add volume data as a new column in the DataFrame
        df['Volume'] = volume_data_reversed

        spy_df = pd.DataFrame(spy_ohlc_data, columns=['Date', 'SPY Close'])
        # Convert date column to datetime format
        spy_df['Date'] = pd.to_datetime(spy_df['Date'], format='%Y-%m-%d')
        spy_df.set_index('Date', inplace=True)  # Set Date column as index

        # Merge ticker DataFrame with SPY DataFrame on Date
        merged_df = df.merge(spy_df, on='Date', how='inner')
        merged_df['RS Ratio'] = merged_df['Close'] / merged_df['SPY Close']

        # Slice the DataFrame for the last 120 days
        df_last_120_days = merged_df.iloc[-120:]

        # Calculate moving averages using only the last 120 days of data
        sma_50 = df['Close'].rolling(window=50).mean()
        ema_10 = df['Close'].ewm(span=10, adjust=False).mean()
        ema_21 = df['Close'].ewm(span=21, adjust=False).mean()

        # Calculate ylim with padding
        ylim_min = df_last_120_days[['Low', 'Close']].min(
        ).min() * 0.95  # 5% below the lowest low or close
        ylim_max = df_last_120_days[['High', 'Close']].max(
        ).max() * 1.05  # 5% above the highest high or close

        mystyle = mpf.make_mpf_style(
            base_mpf_style='yahoo', rc={'font.size': 8, 'figure.facecolor': '#fafafa'},
            gridcolor="#e4e4e7"
        )

        mc = mpf.make_marketcolors(up='#FFFFFF', down='#000000',
                                   edge={'up': '#000000', 'down': '#000000'},
                                   wick={'up': '#000000', 'down': '#000000'},
                                   volume={'up': '#a1a1aa', 'down': '#d4d4d8'},
                                   ohlc='black')

        s = mpf.make_mpf_style(marketcolors=mc)
        print('plotting')

        fig, axlist = mpf.plot(df_last_120_days, type='candle', volume=True, ylabel_lower='Volume', style=mystyle,
                               addplot=[
                                   mpf.make_addplot(
                                       sma_50[-120:], color='#cb4b16', label='50 SMA',  width=.5, panel=0),
                                   mpf.make_addplot(
                                       ema_10[-120:], color='#839496', label='10 EMA', width=.5, panel=0),
                                   mpf.make_addplot(
                                       ema_21[-120:], color='#268bd2', label='21 EMA',  width=.5, panel=0),
                                   mpf.make_addplot(
                                       df_last_120_days['RS Ratio'], color='#000', label='RS Line', width=1, panel=2),
                               ],
                               # figscale=1.10,
                               xlim=(df_last_120_days.index.min(
                               ), df_last_120_days.index.max() + datetime.timedelta(days=5)),
                               ylim=(ylim_min, ylim_max),
                               figsize=(15, 10),
                               panel_ratios=(1, 0.2, .2),
                               scale_padding={
                                   'left': 0.5, 'top': 4, 'right': 3, 'bottom': 1},
                               xrotation=32,
                               returnfig=True,
                               scale_width_adjustment=dict(volume=0.75),
                               tight_layout=True)

        # axlist[0].legend(bbox_to_anchor=(0., 1.02, 1., .102), loc='lower left',
        #                 ncols=3, mode="expand", borderaxespad=0.)
        axlist[0].legend(loc='upper left', borderaxespad=1)
        axlist[4].legend(loc='upper left', borderaxespad=1)
        fig.savefig('fig.png', bbox_inches='tight')

        return upload_to_s3_and_return_link(fig)


def upload_to_s3_and_return_link(fig):
    # Convert the figure to a bytes buffer
    print('saving figure')
    buf = BytesIO()
    fig.savefig(buf, format='png')
    buf.seek(0)

    filename = 'charts/' + str(uuid.uuid4()) + '.png'

    print(filename)

    bucket = boto3.resource('s3').Bucket(bucket_name)
    bucket.put_object(Body=buf, ContentType='image/png', Key=filename)

    # generate presigned url
    url = s3.generate_presigned_url('get_object',
                                    Params={'Bucket': bucket_name,
                                            'Key': filename},
                                    ExpiresIn=86400)

    # Generate the HTTP link to the uploaded image
    # s3_link = s3.generate_presigned_url(
    #    'get_object', Params={'Bucket': bucket_name, 'Key': filename}, ExpiresIn=3600)

    print(url)
    return url


def fetch_data_from_api(ticker):
    try:
        one_year_ago_date = (datetime.datetime.now() -
                             datetime.timedelta(days=365)).strftime('%Y-%m-%d')
        url = f'{base_url}/historical-price-full/{ticker}?apikey={api_key}&from={one_year_ago_date}'
        response = requests.get(url)
        if response.status_code == 200:
            # If the request was successful (status code 200),
            # return the JSON data from the response
            return response.json()
        else:
            # If the request was unsuccessful, raise an exception
            response.raise_for_status()
    except requests.exceptions.RequestException as e:
        # Handle any errors that occurred during the request
        print("Error fetching data:", e)
        return None


def handler(event, context):

    discord_payload = event['Records'][0]['Sns']['Message']
    payload_data = json.loads(discord_payload)

    command_name = payload_data['data']['name']

    # Extract the options
    options = payload_data['data']['options']
    appId = payload_data['application_id']
    token = payload_data['token']

    symbol_value = None

    for option in options:
        if option['name'] == 'symbol':
            symbol_value = option.get('value', None)
            break  # Stop iterating if 'symbol' option is found

    if symbol_value:
        s3_link = make_candlestick_chart(symbol_value)
        embeds = create_embed_with_svg(s3_link, symbol_value)
        print(embeds)
        send_embed_to_discord(embeds, appId, token)

    return ({'statusCode': 200, 'body': 'success'})


def create_embed_with_svg(s3_link, ticker):
    embed = {
        "title": ticker,
        "description": "Daily Chart",
        "image": {
            "url": s3_link
        }
    }
    return embed


def send_embed_to_discord(embed, appid, token):
    discord_webhook_url = f'https://discord.com/api/v10/webhooks/{appid}/{token}'
    headers = {"Content-Type": "application/json"}
    payload = {"embeds": [embed]}
    response = requests.post(
        discord_webhook_url, headers=headers, json=payload)
    print(response.text)  # Print the response from Discord API

    return {
        'statusCode': response.status_code,
        'body': response.text
    }


make_candlestick_chart('NVDL')

from io import BytesIO
import uuid
import mplfinance as mpf
import pandas as pd
import requests
import os
import matplotlib.pyplot as plt
import boto3

base_url = 'https://financialmodelingprep.com/api/v3'
api_key = os.environ.get('FMP_API_KEY')
bucket_name = os.environ.get('CHART_BUCKET')


def make_candlestick_chart(ticker, include_volume=False):
    data = fetch_data_from_api(ticker)
    spy_data = fetch_data_from_api('SPY')
    if data:
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

        mystyle = mpf.make_mpf_style(
            base_mpf_style='yahoo', rc={'font.size': 8})
        fig, axlist = mpf.plot(df_last_120_days, type='candle', volume=True, ylabel_lower='Volume', style=mystyle,
                               addplot=[
                                   mpf.make_addplot(
                                       sma_50[-120:], color='#cb4b16', label='50 SMA',  width=.5, panel=0),
                                   mpf.make_addplot(
                                       ema_10[-120:], color='#839496', label='10 EMA', width=.5, panel=0),
                                   mpf.make_addplot(
                                       ema_21[-120:], color='#268bd2', label='21 EMA',  width=.5, panel=0),
                                   mpf.make_addplot(
                                       df_last_120_days['RS Ratio'], color='#6c71c4', label='RS Line', width=1, panel=2),
                               ],
                               panel_ratios=(7, 1, 2),
                               figratio=(20, 10),
                               figscale=1.5,
                               returnfig=True)

        # axlist[0].legend(bbox_to_anchor=(0., 1.02, 1., .102), loc='lower left',
        #                 ncols=3, mode="expand", borderaxespad=0.)
        axlist[0].legend(loc='upper left', borderaxespad=0.)
        # fig.savefig('fig.svg', bbox_inches='tight')

        upload_to_s3_and_return_link(fig)


def upload_to_s3_and_return_link(fig):
    # Convert the figure to a bytes buffer
    buf = BytesIO()
    fig.savefig(buf, format='svg')
    buf.seek(0)

    filename = 'charts/' + str(uuid.uuid4()) + '.svg'

    # Upload the image to S3
    s3 = boto3.client('s3')
    s3.upload_fileobj(buf, bucket_name, filename)

    # Generate the HTTP link to the uploaded image
    s3_link = s3.generate_presigned_url(
        'get_object', Params={'Bucket': bucket_name, 'Key': filename}, ExpiresIn=3600)

    print(s3_link)
    return s3_link


def fetch_data_from_api(ticker):
    try:
        url = f'{base_url}/historical-price-full/{ticker}?apikey={api_key}&from=2023-01-10'
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


make_candlestick_chart('JPM')

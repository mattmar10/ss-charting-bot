
def calculate_adrp(df, n):
    last_n_rows = df.iloc[-n:]

    daily_range = last_n_rows['High'] - last_n_rows['Low']

    average_daily_range = daily_range.mean()

    last_close_price = df['Close'].iloc[-1]

    # Calculate ADR% as a percentage of the current price
    adrp_percentage = (average_daily_range / last_close_price) * 100

    return adrp_percentage


def calculate_change_last_two_prices(df):
    # Get the last two prices
    last_two_prices = df['Close'].iloc[-2:]

    # Calculate absolute change
    absolute_change = last_two_prices.diff().iloc[-1]

    # Calculate percentage change
    percentage_change = (absolute_change / last_two_prices.iloc[0]) * 100

    return absolute_change, percentage_change

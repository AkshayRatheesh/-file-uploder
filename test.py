import os
try:
    from IIFLapis.order import Order, OrderType, Exchange, ExchangeSegment, OrderValidity, AHPlaced
    from IIFLapis import IIFLClient
except ImportError:
    os.system('python -m pip install IIFLapis==2.1.1')
try:
    import mysql.connector
except ImportError:
    os.system('python -m pip install mysql-connector-python')
try:
    import pandas
except ImportError:
    os.system('python -m pip install pandas==1.4.2')


from IIFLapis import IIFLClient
from IIFLapis.order import Order, OrderType, Exchange, ExchangeSegment, OrderValidity, AHPlaced
import time
import json
import datetime
import sys
import pandas as pd
import mysql.connector

try:
    mydb = mysql.connector.connect(
        host = "manager-app.cmwghd65hb2d.ap-south-1.rds.amazonaws.com",
        user = "admin",
        password = "qUliqeEJRfgEGjVO2drf",
        database="managerapp"
    )

    mycursor = mydb.cursor(dictionary=True)
    sql = "SELECT * FROM trades WHERE id = %s"
    adr = ("31",)
    mycursor.execute(sql, adr)
    myresult = mycursor.fetchone()
    tradevalues = myresult['trade_values']
    tradevalues = json.loads(tradevalues)
    print(tradevalues)

    sqltoken = "SELECT * FROM tradeconfigs WHERE user_id = %s"
    userid = (myresult['user_id'],)
    mycursor.execute(sqltoken, userid)
    mytokenresult = mycursor.fetchone()
    clientdetails=json.loads(mytokenresult['client_details'])
    print(clientdetails)


except Exception as e:
    print(e)
    sys.exit()


try:
    broker_orderIDs=[]
    upper_range = float(tradevalues['upper_limit'])
    lower_range = float(tradevalues['lower_limit'])
    buyData = tradevalues['buy']
    buy_level = float(buyData['entry_price'])
    trailing_stoploss = float(buyData['trailing_stoploss'])
    sl_level = float(buyData['stoploss'])
    # target_level = 215
    gap_condition = True if(tradevalues['gap_filter'] == "ON") else False
    sl_condition = True
    vix_condition = True if(tradevalues['vix_filter'] == "ON") else False
    strike_selection_start_time = tradevalues['strike_selection_start_time']
    strike_selection_end_time = tradevalues['strike_selection_end_time']
    trade_start_time = tradevalues['trade_start_time']
    trade_end_time = tradevalues['trade_end_time']
    qty_to_trade = float(tradevalues['quantity'])
    consider_before_breakout_strike = True
    client_code = clientdetails['ClientCode']
    jwt = clientdetails['JWTToken']
    cookie = clientdetails['IIFLMarCookie']

except:
    print("Wrong Input !!!!")
    sys.exit()


def updatetable(mydb,trade_id,value):
    mycursor = mydb.cursor(dictionary=True)

    sql = "UPDATE trades SET order_book_details = %s WHERE id = %s"
    val = (json.dumps(exchage_orderIDs), trade_id)
    mycursor.execute(sql, val)
    mydb.commit()


def clientLogin():
    global client
    try:
        client = IIFLClient()
        client.outh_login(jwt,cookie)
    except Exception as e:
        time.sleep(1)
        print("Error", e)


def place_trade(scrip_code, quantity, direction, exchange, exchangeType, limit=None):
    try:
        order = Order(order_type=direction,
                      scrip_code=scrip_code,
                      quantity=int(quantity),
                      exchange=exchange,
                      exchange_segment=exchangeType,
                      price=round(limit, 1) if bool(limit) else 0.0,
                      is_intraday=False,
                      atmarket=False if bool(limit) else True,
                      order_id=2,
                      remote_order_id="1",
                      exch_order_id="0",
                      DisQty=0,
                      stoploss_price=0,
                      is_stoploss_order=False,
                      ioc_order=False,
                      is_vtd=False,
                      ahplaced=AHPlaced.NORMAL_ORDER,
                      public_ip='192.168.1.1',
                      order_validity=OrderValidity.DAY,
                      traded_qty=0
                      )
        return client.place_order(order=order, client_id=client_code, order_requester_code=client_code)
    except Exception as e:
        print('Error : ', e)
        return f"{e}"


def cancel_order(exch_order_id, scrip_code, quantity, direction, exchange, exchangeType, limit=None):
    try:
        order_to_cancel = Order(order_type=direction,
                                scrip_code=scrip_code,
                                quantity=int(quantity),
                                exchange=exchange,
                                exchange_segment=exchangeType,
                                price=round(limit, 1) if bool(limit) else 0.0,
                                is_intraday=True,
                                atmarket=False if bool(limit) else True,
                                exch_order_id=exch_order_id)
        client.cancel_order(order=order_to_cancel, client_id=client_code,
                            order_requester_code=client_code)
    except Exception as e:
        print('Error : ', e)
        return f"{e}"


def get_filled_qty(order_data):
    try:
        order_book = client.order_book(client_id=client_code)
        for order in order_book:
            if (order["ExchOrderID"] == order_data["ExchOrderID"]):
                return order["TradedQty"]
        # raise Exception("Sorry, no orders")
    except Exception as e:
        return f"{e}"


def get_strike(symbol_name, price):
    global main_df, lot_size
    while True:
        try:
            main_df
            break
        except:
            try:
                df = client.ScripMaster
                df = df[df["UnderlyingScripName"] == symbol_name]
                df = df[df["ExchType"] == "D"]
                main_df = df[df["Expiry"] == sorted(
                    list(df["Expiry"].unique()))[0]]
                lot_size = float(list(main_df["LotSize"])[0])
            except Exception as e:
                pass

    def closest(lst, K):
        return lst[min(range(len(lst)), key=lambda i: abs(lst[i] - K))]
    strike = float(closest(list(main_df["StrikeRate"]), price))
    return (main_df[((main_df["StrikeRate"] >= (
        strike - 1000)) & (main_df["StrikeRate"] <= (strike + 1000)))][["StrikeRate", "CpType", "Name", "Scripcode", "Exch", "ExchType"]].to_dict('records'))


def getLTP(req_list):
    market_feed_strike_list = [{"Exch": req_elem["Exch"], "ExchType": req_elem["ExchType"],
                                "ScripCode": req_elem["Scripcode"]} for req_elem in req_list]
    ltp_data = client.fetch_market_feed(
        req_list=market_feed_strike_list, count=len(market_feed_strike_list), client_id=client_code)["Data"]
    final_list = {req_list[i]['Scripcode']: {**req_list[i], **ltp_data[i]}
                  for i in range(len(req_list))}
    return final_list


def strategy():
    global ltp, strike_ltp, sl_level
    todate = str(datetime.datetime.today().date())
    print("-------Algo Started-------")
    a, b = (int(strike_selection_start_time.split(":")[0]), int(
        strike_selection_start_time.split(":")[1]))
    a = 23 if (b == 0 and a == 0) else (a-(1 if b == 0 else 0))
    b = 59 if b == 0 else b-1
    while datetime.datetime.now().time() <= (datetime.time(a, b)):
        time.sleep(1)
    while True:
        try:
            historic_data = client.historical_candles(exch='n', exchType='c', scripcode='999920000', interval='1d',
                                                      fromdate='2023-04-25', todate=todate, client_id=client_code)
            mar_open = historic_data['data']['candles'][0][1]
            mar_prev_close = historic_data['data']['candles'][0][4]
            ltp = historic_data['data']['candles'][0][4]
            if gap_condition:
                change_point = mar_open - mar_prev_close
            else:
                change_point = 0
            break
        except Exception as e:
            time.sleep(1)
    got_strikes = get_strike("NIFTY", ltp)
    strikes = {}
    selected_strikes = []
    while True:
        try:
            strike_ltp = {}
            for k, v in getLTP(got_strikes).items():
                if ((change_point >= 200 and v["CpType"] == "PE") or change_point <= 100) and change_point >= -100:
                    strike_ltp[k] = v["LastRate"]
                    strikes[k] = v
            break
        except Exception as e:
            time.sleep(1)
            print(e)
    while datetime.time(int(strike_selection_end_time.split(":")[0]), int(strike_selection_end_time.split(":")[1])) > datetime.datetime.now().time():
        if datetime.datetime.now().time() >= datetime.time(int(strike_selection_start_time.split(":")[0]), int(strike_selection_start_time.split(":")[1])):
            while True:
                try:
                    strike_ltp = {k: v["LastRate"]
                                  for k, v in getLTP(list(strikes.values())).items()}
                    break
                except Exception as e:
                    time.sleep(1)
            for i in strike_ltp.keys():
                if upper_range >= strike_ltp[i] >= lower_range and i not in selected_strikes:
                    print(i, strike_ltp[i])
                    selected_strikes.append(i)
        time.sleep(0.5)
    if not consider_before_breakout_strike:
        print("Selected Strikes : ", selected_strikes)
    strikes_for_trading_breakout = [] if consider_before_breakout_strike else selected_strikes
    traded = None
    order_data = None
    india_vix = None
    while selected_strikes:
        time.sleep(1)
        while True:
            try:
                strike_ltp = {k: v["LastRate"]
                              for k, v in getLTP(list(strikes.values())).items()}
                break
            except:
                time.sleep(1)
        if not consider_before_breakout_strike and datetime.datetime.now().time() < datetime.time(int(trade_start_time.split(":")[0]), int(trade_start_time.split(":")[1])):
            for i in strikes_for_trading_breakout:
                if strike_ltp[i] >= buy_level:
                    strikes_for_trading_breakout.remove(i)
                    print("Removed Strike : ", i)
        if datetime.time(int(trade_end_time.split(":")[0]), int(trade_end_time.split(":")[1])) >= datetime.datetime.now().time() >= datetime.time(int(trade_start_time.split(":")[0]), int(trade_start_time.split(":")[1])):
            if india_vix is None:
                while True:
                    try:
                        # india_vix_data = kite.quote(["NSE:INDIA VIX"])["NSE:INDIA VIX"]
                        dt = '2023-04-25'
                        nd = '2023-04-26'
                        india_vix_data = client.historical_candles(exch='n', exchType='d', scripcode='999920019',
                                                                   interval='1d',
                                                                   fromdate=dt, todate=nd, client_id=client_code)
                        india_vix_ltp = india_vix_data['data']['candles'][1][4]
                        india_vix_open = india_vix_data['data']['candles'][1][4]
                        if vix_condition and india_vix_ltp > india_vix_open * 1.01 and india_vix_ltp > 20:
                            india_vix = True
                        elif not vix_condition:
                            india_vix = True
                        else:
                            india_vix = False
                        break
                    except:
                        time.sleep(1)
            if not india_vix:
                print("India VIX not Satisfied!!!!")
                print("Trading Done.")
                break
            if traded is None and india_vix:
                for i in selected_strikes:
                    if consider_before_breakout_strike and strike_ltp[i] <= buy_level - 1 and i not in strikes_for_trading_breakout:
                        strikes_for_trading_breakout.append(i)
                        print("Added Strike : ", i)
                for i in strikes_for_trading_breakout:
                    if strike_ltp[i] >= buy_level and traded is None:
                        traded = i
                        order_data = place_trade(
                            strikes[i]['Scripcode'], qty_to_trade, "BUY", strikes[i]['Exch'], strikes[i]['ExchType'], limit=buy_level)
                        BrokerOrderID = order_data['BrokerOrderID']
                        if BrokerOrderID != 0:
                            broker_orderIDs.append(BrokerOrderID)
        if traded is not None:
            if sl_condition and strike_ltp[traded] > trailing_stoploss and int(strike_ltp[traded]) - 10 > sl_level:
                sl_level = int(strike_ltp[traded]) - 10
                print("Sl Trail : ", sl_level)
            if strike_ltp[traded] <= sl_level or datetime.datetime.now().time() >= datetime.time(15, 15):
                cancel_order(order_data["ExchOrderID"],
                             strikes[traded]["Scripcode"],
                             qty_to_trade, "BUY", strikes[traded]['Exch'], strikes[traded]['ExchType'])
                time.sleep(1.5)
                place_trade_data=place_trade(
                    strikes[i]['Scripcode'], get_filled_qty(order_data), "SELL", strikes[i]['Exch'], strikes[i]['ExchType'], limit=buy_level)
                BrokerOrderID = place_trade_data['BrokerOrderID']
                if BrokerOrderID != 0:
                    broker_orderIDs.append(BrokerOrderID)

                trade_book_data=client.trade_book(client_id)
                updatetable(mydb, trade_id, trade_book_data)
                print("Trading Done.")
                break
    else:
        print("No strike in your price range...")

    print("-----Algo Stopped-----")


if __name__ == '__main__':
    clientLogin()
    strategy()

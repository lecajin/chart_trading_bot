import ccxt
import time
import talib
import pandas as pd
import logging
import datetime
import math
import telegram

logger = logging.getLogger()
logger.setLevel(logging.ERROR)
file_handler = logging.FileHandler(filename="error.log")
logger.addHandler(file_handler)

telegm_token = ''
bot = telegram.Bot(token = telegm_token)

coin_list = []

exchange = ccxt.upbit({'apiKey':'',
                    'secret':'',
                    'enableRateLimit': True
                    })

'''
exchange = ccxt.bithumb({'apiKey':'',
                    'secret':'',
                    'enableRateLimit': True
                    })
'''
def run():
    now = datetime.datetime.now()
    mid = datetime.datetime(now.year, now.month, now.day) + datetime.timedelta(1) # 익일 자정
    nextDay = mid + datetime.timedelta(hours=9)  #익일 자정 + 9시간 --> 익일 오전 9시
    coin_list = getCoinData() # 거래할 코인 리스트 불러옴
    coin_list_dic = {}
    for ticker in coin_list:
        coin_list_dic[ticker] = {}
        coin_list_dic[ticker]['isSendMsg'] = False

    while True:
        try:
            now = datetime.datetime.now() #현시간
            if nextDay < now:
                mid = datetime.datetime(now.year, now.month, now.day) + datetime.timedelta(1) # 익일 자정
                nextDay = mid + datetime.timedelta(hours=9)
                coin_list = getCoinData() # 오전 9시 거래할 코인 리스트를 새로 불러옴
                sendTelegramMsg('refresh coin list')
            time.sleep(0.1)

            for ticker in coin_list:
                avgBuyPrice = float(getAvgBuyPrice(ticker)) # 매수 평균가 조회 ※빗썸에서는 매수 평균가 조회 기능을 지원하지 않는 것 같음. 빗썸으로 거래할 경우 해당 로직은 주석처리 해야 함.
                #tickerAmt = getTickerAmt(ticker) #가지고 있는 코인 수량을 조회. 빗썸거래소 사용할 경우 이부분을 사용해야 함.
                rsiSignal = getRSISignal(ticker)
                stochSignal =  getStochSignal(ticker)
                print('=====================[ ' + ticker + ' ]====================')
                print('rsiSignal : ' + str(rsiSignal))
                print('stochSignal : ' + str(stochSignal))
                print('====================================================')
                #BBSignal = getBBSignal(ticker)
                #mfiSignal = getMFISignal(ticker)
                #macdSignal = getMACDSignal(ticker)
                #ichimokuSignal = getIchimoku(ticker)

                if rsiSignal == 1 and stochSignal == 1:
                    balance = getBalance()  # 잔고조회
                    invest_price = float(balance) * 0.1 # 잔고의 10%만 투자한다고 했을때..

                    if invest_price < 5000:  # 업비트는 최소 구매금액이 5천원 이상이다.
                        continue # 투자금액이 미달되므로 다음 코인으로 넘어간다.

                    if avgBuyPrice == 0.0: # 매수평균가가 0이면 즉, 매수한 적이 없으면
                    #if tickerAmt == 0.0:  # 매수한 코인이 없으면..(빗썸을 사용할 경우 이것을 사용해야함.)
                        buyTransNo = market_buy_upbit(ticker, invest_price) # 시장가매수

                        #order_price = getBuyOrderPrice(ticker, 1) # 최우선 다음 매수호가 조회. 최우선 매수호가 조회시 0을 입력
                        #buy_amt = invest_price / order_price # 투자금액으로 구매가능한 수량
                        #buyTransNo = limit_buy_upbit(ticker, buy_amt, order_price) #지정가 매수
                        if buyTransNo is not None:
                            print(ticker + ' buy!!')
                            if not coin_list_dic[ticker]['isSendMsg']: # 텔레그램 메시지를 보내지 않았으면 즉 False면.
                                sendTelegramMsg(ticker + '매수완료')
                                coin_list_dic[ticker]['isSendMsg'] = True # 텔레그램 메시지 보냈다라고 체크.

                if rsiSignal < 0 and stochSignal < 0:
                    unit = float(getTickerAmt(ticker))
                    if unit > 0.0:  # 보유하고 있는 가상화폐가 존재하면
                        order_price = getSellOrderPrice(ticker, 1) # 최우선 다음 매도호가 조회. 최우선 매도호가 조회시 0을 입력
                        sellTransNo = limit_sell_upbit(ticker, unit, order_price) # 지정가 매도
                        #sellTransNo = market_sell_upbit (ticker, unit)  # 시장가 매도
                        if sellTransNo is not None:
                            print(ticker + ' sell!!')
                            sendTelegramMsg(ticker + '매도완료')
                            coin_list_dic[ticker]['isSendMsg'] = False # 향후 매수 메시지를 받기위해 False로 되돌림.

                time.sleep(0.1)

        except Exception as e:
            try:
                print(e)
            except:
                pass


# 잔고조회
def getBalance():
    bal = exchange.fetch_balance()
    return bal['KRW']['free'] # 업비트
    #return bal['info']['data']['available_krw'] # 빗썸

# 암호화폐 보유수량 조회
def getTickerAmt(ticker):
    tickerAmt = exchange.fetch_balance()
    try:
        charPosition = ticker.find('/')  # ETH/KRW라고 되었을때 '/'의 위치를 찾는다. 이때 charPosition은 3이된다.
        return tickerAmt[ticker[0:charPosition]]['free']
    except:
        return 0

# 차트정보 조회
def getCandleStick(ticker, period):
    if period == '10m':
        ohlcv_10m = []  # 10분 봉을 얻기위함.
        timestpam = 0
        open = 1
        high = 2
        low = 3
        close = 4
        volume = 5

        ohlcv = exchange.fetch_ohlcv(ticker, '5m')

        while ohlcv is None:
            time.sleep(0.1)
            ohlcv = exchange.fetch_ohlcv(ticker, '5m')  # 5분 봉을 가져온다.
        if len(ohlcv) > 2:  # 10분봉을 만드는 부분
            for i in range(0, len(ohlcv) - 1, 2):
                highs = [ohlcv[i + j][high] for j in range(0, 2) if ohlcv[i + j][high]]
                lows = [ohlcv[i + j][low] for j in range(0, 2) if ohlcv[i + j][low]]
                volumes = [ohlcv[i + j][volume] for j in range(0, 2) if ohlcv[i + j][volume]]
                candle = [
                    ohlcv[i + 0][timestpam],
                    ohlcv[i + 0][open],
                    max(highs) if len(highs) else None,
                    min(lows) if len(lows) else None,
                    ohlcv[i + 1][close],
                    sum(volumes) if len(volumes) else None
                ]
                ohlcv_10m.append((candle))
        dataframe = pd.DataFrame(ohlcv_10m, columns=['date', 'open', 'high', 'low', 'close', 'volume'])
        return dataframe

    else:
        ohlcv = exchange.fetch_ohlcv(ticker, period)
        dataframe = pd.DataFrame(ohlcv, columns=['date', 'open', 'high', 'low', 'close', 'volume'])
        return dataframe

# 거래가능한 코인리스트 조회
def getCoinData():
    totalCoinList = []
    coins = exchange.fetch_tickers() #전체 코인 리스트를 불러옴.
    tickerList = coins.keys() #딕셔너리 형태이므로 Key값(코인 이름)만 가져옴.
    for coin in tickerList:
        if coin[-3:] == 'KRW': #코인의 이름에서 마지막 3글자가 KRW이면.
            totalCoinList.append(coin) # 그 코인을 새로운 리스트에 담는다.
    return totalCoinList

# 현재가 조회
def getCurrPrice(ticker):
    currPrice = 0
    while currPrice == 0:
        currPrice = exchange.fetch_ticker(ticker)['close']
        time.sleep(0.1)
    return currPrice

#=========================기술적 분석==========================

# 볼린저 밴드
def getBBSignal(ticker):
    df = getCandleStick(ticker, '5m')  # 가상화폐의 5분봉 DATA를 조회.
    curPrice = getCurrPrice(ticker)
    upper, middle, lower = talib.BBANDS(df['close'], 20, 2)  # 종가, 길이, 곱
    b = ((curPrice - lower.iloc[-1]) / (upper.iloc[-1] - lower.iloc[-1])) * 100

    if b >= 80:
        return 1  # 매수 시그널
    elif b <= 20:
        return -1  # 매도 시그널
    else:
        return 0  # 관망

# MFI
def getMFISignal(ticker):
    df = getCandleStick(ticker, '5m')  # 가상화폐의 5분봉 DATA를 조회.
    mfi = talib.MFI(df['high'], df['low'], df['close'], df['volume'], 10) # 고가, 저가, 종가, 거래량, 기간
    nowMFI = mfi.iloc[-1]  # 가장 최신의 MFI값을 가져옴.

    if nowMFI >= 80.0:
        return 1 # 매수 시그널
    elif nowMFI <= 20:
        return -1 # 매도 시그널
    else:
        return 0

# RSI
def getRSISignal(ticker):
    df = getCandleStick(ticker, '5m')
    rsi14 = talib.RSI(df['close'], 14) # 종가, 기간
    nowRsi = rsi14.iloc[-1]  # 가장 최근의 RSI값

    if nowRsi <= 30.0:  # 과매도
        return 1  # 매수 시그널
    elif nowRsi >= 70.0:  # 과매수
        return -1  # 매도 시그널
    else:
        return 0

# MACD
def getMACDSignal(ticker):
    df = getCandleStick(ticker, '5m')
    macd, macdSignal, macdHist = talib.MACD(df['close'], 12, 26, 9) # MACD 단기 12이평선, MACD 장기 26이평선, 시그널은 9 이평선

    if macd.iloc[-1] >= macdSignal.iloc[-1] and macd.iloc[-2] < macdSignal.iloc[-2]: # macd가 골든크로스
        return 1 #매수 시그널
    elif macd.iloc[-1] <= macdSignal.iloc[-1] and macd.iloc[-2] > macdSignal.iloc[-2]: # macd 데드크로스
       return -1 #매도 시그널
    else:
        return 0

# 스토캐스틱
def getStochSignal(ticker):
    df = getCandleStick(ticker, '5m') # 5분봉
    slowk, slowd = talib.STOCH(df['high'], df['low'], df['close'], fastk_period=12, slowk_period=5, slowd_period=5)

    # 현재 K선이 20이하 이고, 과거에는 K선이 D선보다 아래에 있다가 현재 K선이 D선보다 맞닿아 있거나 위에 있으면.
    if slowk.iloc[-1] <= 20.0 and (slowk.iloc[-2] < slowd.iloc[-2]) and (slowk.iloc[-1] >= slowd.iloc[-1]):
        return 1 # 매수 시그널
    # 현재 K선이 80이상 이고, 과거에는 K선이 D선보다 위에 있다가 현재 K선이 D선보다 맞닿아 있거나 아래에 있으면.
    elif slowk.iloc[-1] >= 80 and (slowk.iloc[-2] > slowd.iloc[-2]) and (slowk.iloc[-1] <= slowd.iloc[-1]):
        return -1  # 매도 시그널
    else:
        return 0  # 관망

# 단순이동평균
def getSMA(ticker, period):
    df = getCandleStick(ticker, '1d') #일봉을 가져온다.
    ma5 = talib.SMA(df['close'], period) # n일선을 가져온다.
    return ma5.iloc[-1]

# 일목균형표
def getIchimoku(ticker):
    df = getCandleStick(ticker, '5m')

    period9_high = df['close'].rolling(window=9).max()
    period9_low = df['close'].rolling(window=9).min()

    # 전환선
    tenkan_sen = (period9_high + period9_low) / 2

    period26_high = df['close'].rolling(window=26).max()
    period26_low = df['close'].rolling(window=26).min()

    # 기준선
    kijun_sen = (period26_high + period26_low) / 2

    #후행스팬
    chikou_span = df.shift(-26)

    # 선행스팬 A
    senkou_span_a = ((tenkan_sen + kijun_sen) / 2).shift(26)

    period52_high = df['close'].rolling(window=52).max()
    period52_low = df['close'].rolling(window=52).min()

    # 선행스팬 B
    senkou_span_b = ((period52_high + period52_low) / 2).shift(26)

    curPrice = getCurrPrice(ticker)

    if tenkan_sen.iloc[-1] > kijun_sen.iloc[-1] and tenkan_sen.iloc[-2] <= kijun_sen.iloc[-2]: #전환선이 기준선 상향돌파
        if curPrice > senkou_span_a.iloc[-1] and curPrice > senkou_span_b.iloc[-1]: # 주가가 구름대 상향돌파
            return 1
    elif tenkan_sen.iloc[-1] < kijun_sen.iloc[-1] and tenkan_sen.iloc[-2] >= kijun_sen.iloc[-2]: #전환선이 기준선 하향돌파
        return -1
    elif curPrice < senkou_span_a.iloc[-1] and curPrice < senkou_span_b.iloc[-1]: #주가가 구름대 하향돌파
        return -1
    else:
        return 0


#=========================청산 기법==========================

# 파라볼릭 SAR
def getPSAR(ticker):
    df = getCandleStick(ticker, '3m')
    sar = talib.SAR(df['high'], df['low'], acceleration=0.02, maximum=0.2)
    nowSAR = sar.iloc[-1]
    curPirce = getCurrPrice(ticker)
    if float(curPirce) < float(nowSAR): #현재 가격이 SAR보다 아래에 있으면 매도
        return -1
    else:
        return 0

# 샹들리에 출구전략
def getChandelierExit(ticker):
    df = getCandleStick(ticker, '3m')
    df20 = df.iloc[-21:-1] # 3분봉기준이므로 1시간의 차틎어보가 되겠다.
    maxPrice = df20['high'].max() #최근 1시간동안의 최고가를 변수에 지정
    atr = talib.ATR(df['high'], df['low'], df['close'], timeperiod = 20).iloc[-1]
    stopPrice = maxPrice - 2.5 * atr #청산가격 설정
    curPirce = getCurrPrice(ticker)
    if float(curPirce) < float(stopPrice):
        return -1
    else:
        return 0

#=========================매수 및 매도==========================

# 업비트 시장가 매수
def market_buy_upbit(ticker, invest_price):
    try:
        krw = invest_price
        exchange.options = {'createMarketBuyOrderRequiresPrice': False}
        buy_order = exchange.create_market_buy_order(ticker, krw)  # 시장가 매수 업비트는 금액을 넣는다.
        return buy_order
    except Exception as e:
        print(e)
        pass

# 업비트 지정가 매수
def limit_buy_upbit(ticker, unit, order_price):
    try:
        buy_order = exchange.create_limit_buy_order(ticker, unit, order_price)
        return buy_order
    except Exception as e:
        print(e)
        pass

# 업비트 시장가 매도
def market_sell_upbit(ticker, unit):
    try:
        sell_order = exchange.create_market_sell_order(ticker, unit)
        return sell_order
    except Exception as e:
        print(e)
        pass

# 업비트 지정가 매도
def limit_sell_upbit(ticker, unit, order_price):
    try:
        sell_order = exchange.create_limit_sell_order(ticker, unit, order_price)
        return sell_order
    except Exception as e:
        print(e)
        pass

# 빗썸 시장가 매수
def market_buy_bithumb(ticker, invest_price):
    try:
        krw = invest_price
        orderbook = exchange.fetch_order_book(ticker)
        sell_price = orderbook['asks'][0][0]
        unit = krw / sell_price
        buy_order = exchange.create_market_buy_order(ticker, unit)  # 시장가 매수
        return buy_order
    except Exception as e:
        print(e)
        pass

# 빗썸 지정가 매수
def limit_buy_bithumb(ticker, unit, order_price):
    try:
        buy_order = exchange.create_limit_buy_order(ticker, unit, order_price)
        return buy_order
    except Exception as e:
        print(e)
        pass

# 빗썸 시장가 매도
def market_sell_bithumb(ticker, unit):
    try:
        sellUnit = math.floor(unit*10000)/10000 #빗썸은 소수점 4째자리까지만 매도수량을 받는다.
        if sellUnit > 0.0:
            sell_order = exchange.create_market_sell_order(ticker, sellUnit)
            return sell_order
    except Exception as e:
        print(e)
        pass

# 빗썸 지정가 매도
def limit_sell_bithumb(ticker, unit, order_price):
    try:
        sellUnit = math.floor(unit*10000)/10000 #빗썸은 소수점 4째자리까지만 매도수량을 받는다.
        if sellUnit > 0.0:
            sell_order = exchange.create_limit_sell_order(ticker, sellUnit, order_price)
            return sell_order
    except Exception as e:
        print(e)
        pass

# 매수평균단가 구하기
def getAvgBuyPrice(ticker):
    bal = exchange.fetch_balance()
    hasList = {}
    for i in range(1, len(bal['info'])):
        hasList[bal['info'][i]['currency']] = bal['info'][i]['avg_buy_price']
    charPosition = ticker.find('/')
    tickerName = ticker[0:charPosition]
    if tickerName in hasList:
        return hasList[tickerName] #매수 평균가
    else:
        return 0

# 매수호가 가격 조회
def getBuyOrderPrice(ticker, rank):
    orderbook = exchange.fetch_order_book(ticker)
    buy_price = orderbook['bids'][rank][0] # 매수호가
    return buy_price

# 매도호가 가격 조회
def getSellOrderPrice(ticker, rank):
    orderbook = exchange.fetch_order_book(ticker)
    sell_price = orderbook['asks'][rank][0] # 매도호가
    return sell_price

# 텔레그램 메시지 보내기
def sendTelegramMsg(msg):
    bot.sendMessage(chat_id='', text=msg)

if __name__ == '__main__':
    run()
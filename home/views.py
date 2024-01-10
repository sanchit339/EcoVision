import os

from django.shortcuts import render
import matplotlib

matplotlib.use('Agg')
import matplotlib.pyplot as plt
import requests
from datetime import datetime, time, date, timedelta
import numpy as np
import pandas as pd
from statsmodels.tsa.arima.model import ARIMA
from pmdarima.arima import auto_arima
import pickle

api_key = os.environ.get('api_key')  # I have used OpenWeatherMap API's Student pack benefits.


# Create your views here.

def getCoordinates(cityname):
    url = f'http://pro.openweathermap.org/geo/1.0/direct?q={cityname}&limit=1&appid={api_key}'
    response = requests.get(url)
    cityData = response.json()
    if len(cityData) == 0:
        coordinates = {}
        return coordinates
    else:
        latitude = cityData[0]['lat']
        longitude = cityData[0]['lon']
        coordinates = {'latitude': latitude, 'longitude': longitude}
        # print(coordinates)
        return coordinates


# to get each pollutant's concentration
def pollutantConcentration(latitude, longitude):
    url = f'http://pro.openweathermap.org/data/2.5/air_pollution?lat={latitude}&lon={longitude}&appid={api_key}'
    response = requests.get(url)
    citypollutants = response.json()
    citypollutants = citypollutants['list'][0]['components']
    return citypollutants


def chartGeneration(concentrations):
    pollutants = []
    concs = []
    for pollutant, conc in concentrations.items():
        pollutants.append(pollutant)
        concs.append(conc)

    plt.clf()
    plt.pie(concs, labels=pollutants, autopct='%1.1f%%')
    chart_path = 'home/static/home/chart.jpg'
    static_path = 'home/chart.jpg'
    plt.savefig(chart_path)
    plt.close()
    return static_path


def dataSetCreation(placeCoordinates):
    endtime = datetime.combine(date.today(), time.min)
    starttime = endtime - timedelta(days=6 * 30)  # taking 6 months ago as start time for data extraction.

    # converting to unix format for api request
    start = int(starttime.timestamp())
    end = int(endtime.timestamp())

    url = f'http://pro.openweathermap.org/data/2.5/air_pollution/history?lat={placeCoordinates["latitude"]}&lon={placeCoordinates["longitude"]}&start={start}&end={end}&appid={api_key}'  # historical data
    response = requests.get(url)
    dt = response.json()
    if 'list' not in dt:
        # Handle the case where 'list' key is not present in the response
        return pd.DataFrame()

    histData = dt['list']

    dfs = []
    for record in histData:
        if 'aqi' not in record['main']:
            # Handle the case where 'aqi' key is not present in a record
            continue
        row = {
            'aqi': record['main']['aqi'],
            'date': record['dt'],
        }
        row.update(record['components'])
        df = pd.DataFrame(row, index=[0])
        dfs.append(df)

    if not dfs:
        # Handle the case where no valid records were found
        return pd.DataFrame()

    df = pd.concat(dfs, ignore_index=True)

    return df


def dataPreprocessing(df):
    subset = ['aqi', 'co', 'no', 'no2', 'o3', 'so2', 'pm2_5', 'pm10', 'nh3']
    for column in subset:
        df[column].fillna(df[column].mean(), inplace=True)

    df['date'] = df['date'].fillna(method='ffill')
    df['date'] = pd.to_datetime(df['date'], unit='s')

    return df


# creating separate dataFrame for Modeling
def modelingDataFrame(df):
    model_df = pd.DataFrame()
    model_df['date'] = df['date']
    model_df['co'] = df['co']

    model_df = model_df.rename(columns={'date': 'datetime'})
    model_df.set_index('datetime', inplace=True)
    return model_df


def trainingModel(training_df):
    model = auto_arima(training_df['co'], seasonal=False, trace=True)
    model = ARIMA(training_df['co'].astype(float), order=(3, 1, 3))
    arima_model = model.fit()
    return arima_model


def foreCast(arima_model, training_df):
    forecast_period = 30  # Example: Forecasting CO concentrations for the next 30 days
    predictions = arima_model.forecast(steps=forecast_period)
    predictions = predictions.tolist()
    # Create a date range for the forecasted period
    start_date = training_df.index.max() + pd.DateOffset(days=1)
    end_date = start_date + pd.DateOffset(days=forecast_period - 1)
    date_range = pd.date_range(start=start_date, end=end_date, freq='d')

    predictions_df = pd.DataFrame({'datetime': date_range, 'co': predictions})
    return predictions_df


def TimeSeriesGraphGeneration(predictions_df):
    plt.clf()
    plt.figure(figsize=(12, 6))
    plt.plot(predictions_df['datetime'], predictions_df['co'])
    plt.title('Forecasted CO Concentration Time Series')
    plt.xlabel('Datetime')
    plt.ylabel('CO Concentration')
    figure_path = 'home/static/home/analysis.jpg'
    static_path = 'home/analysis.jpg'
    plt.savefig(figure_path)
    plt.close()
    return static_path


def prediction(request):
    if request.method == 'POST':
        city = request.POST['CityName']
        placeCoordinates = getCoordinates(city)
        if len(placeCoordinates) == 0:
            return render(request, 'home/noData.html')
        else:
            df = dataSetCreation(placeCoordinates)
            preProcessedData = dataPreprocessing(df)
            trainingModelFrame = modelingDataFrame(preProcessedData)
            trainedModel = trainingModel(trainingModelFrame)
            predictedData = foreCast(trainedModel, trainingModelFrame)

            static_path = TimeSeriesGraphGeneration(predictedData)
            return render(request, 'home/predictionPage.html', {'analysispath': static_path, 'city': city})
    else:
        return render(request, 'home/getCityForPrediction.html')


def home(request):
    if request.method == 'POST':
        city = request.POST['CityName']
        placeCoordinates = getCoordinates(city)
        if len(placeCoordinates) == 0:
            return render(request, 'home/noData.html')
        else:
            concentrations = pollutantConcentration(placeCoordinates['latitude'],
                                                    placeCoordinates['longitude'])  # pollutants concentrations in μg/m3

            static_path = chartGeneration(concentrations)
            return render(request, 'home/homepage.html', {'chartpath': static_path, 'city': city})
    else:
        return render(request, 'home/getCityName.html')

import time
import pytz
import os
import urllib.request
from datetime import datetime
from influxdb import InfluxDBClient
import json
import xml.etree.ElementTree as ET

#=========Init===========

testmode = 0
#testmode == 1 is test
#testmode == 0 is normal


local_tz = pytz.timezone ("Australia/Sydney")

if testmode == 0:
  xmlfileloc =  '/home/pi/python/weather.xml'
  csvfileloc = '/home/pi/python/weather.csv'
  webloc = '/home/pi/python/web/'
  database = 'weather'
  
else: 
  xmlfileloc = '/home/pi/pythont/weather.xml'
  csvfileloc = '/home/pi/pythont/weather.csv'
  webloc = '/home/pi/pythont/web/'
  database = 'test'


#=========Read file with the Weatherlink link================
if testmode == 0:
  c = open('/home/pi/python/xmllink.txt','r')
  xmllink = c.read().replace('\n', '')
  c.close
  grafanaauthfile = open('/home/pi/python/grafanaauth.txt','r')
else:
  xmllink = 'http://jimbotis.ddns.net/weather/weather.xml'
  grafanaauthfile = open('/home/pi/pythont/grafanaauth.txt','r')
  
grafanaauth = grafanaauthfile.read().replace('\n', '')
grafanaauthfile.close

#=======Download the file and save contents to a local file==============
contents = urllib.request.urlopen(xmllink)
contentsbyte = contents.read()
weatherxml = contentsbyte.decode("utf8")
contents.close()
 
d = open(xmlfileloc,'w')
d.write(weatherxml)
d.close

root = ET.fromstring(weatherxml)
readings = dict()

e = open(csvfileloc,'w')

#============Read the downloaded XML file and store in a dictionary.  Any values in imperial measurements are converted=============
#============First level measurements in the XML structure====================
for child in root:
  readname = child.tag.split("_")
  if readname[-1] == 'rfc822':
    recordedtime = child.text

  e.write(child.tag + "|" + child.text + "\n")
  readings[child.tag] = child.text
  if readname[-1] == 'kt':
    wind_kph = round(float(child.text) * 1.852,1)
    #print wind_kph
    e.write("wind_kph|" + str(wind_kph) + "\n")
    readings["wind_kph"] = wind_kph

    
#============Second level measurements in the XML structure===================    
for child in root[34]:
  readname2 = child.tag.split("_")
  if readname2[-1] == "f":
    value_c = round((float(child.text) - 32) *5/9,1)
    e.write(child.tag[:-1] + "c|" + str(value_c) + "\n")
    readings[child.tag[:-1] + "c"] = float(value_c)
  elif readname2[-1] == 'mph':
    value_kph = round((float(child.text) * 1.609344),1)
    e.write(child.tag[:-3] + "kph|" + str(value_kph) + "\n")
    readings[child.tag[:-3] + "kph"] = float(value_kph)
  elif str(child.tag)[:4] == "rain" and str(child.tag).find("_in") > 0:
    value_mm = round(float(child.text) * 25.4,1)
    e.write(str(child.tag).replace("_in","_mm") + "|" + str(value_mm) + "\n")
    readings[str(child.tag).replace("_in","_mm")] = float(value_mm)
  elif readname2[0] == "et":
    et_mm = round(float(child.text) * 25.4,1)
    e.write(str(child.tag) + "_mm|" + str(et_mm) + "\n")
    readings[str(child.tag) + "_mm"] = float(et_mm)
  else:
    e.write(child.tag + "|" + child.text + "\n")
    readings[child.tag] = child.text  

e.close


#==========InfluxDB requires timestamp in UTC.  This section converts the time into UTC.=============
splittime = recordedtime.split(" ")
#Create timestamp from Weatherlink output
newtime = datetime.strptime(splittime[3] + " " + splittime[2] + " " + splittime[1] + " " + splittime[4], '%Y %b %d %H:%M:%S')
#Convert local time to UTC
datetime_with_tz = local_tz.localize(newtime, is_dst=None) # No daylight saving time
datetime_in_utc = datetime_with_tz.astimezone(pytz.utc)

#=========This is the json payload that gets inserted into InfluxdB==========
json_body = [
  {"measurement": "weather","time": datetime_in_utc,"fields": {
"temp": float(readings['temp_c']),
"temp_in": float(readings['temp_in_c']),
"windchill": float(readings['windchill_c']),
"dewpoint": float(readings['dewpoint_c']),
"head_index_c": float(readings['heat_index_c']),

"pressure": float(readings['pressure_mb']), 

"wind_kph": float(readings['wind_kph']),
"wind_degrees": float(readings['wind_degrees']),
"wind_ten_min_gust_kph": float(readings['wind_ten_min_gust_kph']),
"wind_ten_min_avg_kph": float(readings['wind_ten_min_avg_kph']),

"rain_day_mm": float(readings['rain_day_mm']),
"rain_month_mm": float(readings['rain_month_mm']),
"rain_year_mm": float(readings['rain_year_mm']),
"rain_storm_mm": float(readings['rain_storm_mm']),
"rain_rate_mm_per_hour": float(readings['rain_rate_mm_per_hr']),

"relative_humidity": int(readings['relative_humidity']),
"relative_humidity_in": int(readings['relative_humidity_in']),

"solar": float(readings['solar_radiation']),

"et_day_mm": float(readings['et_day_mm']),
"et_month_mm": float(readings['et_month_mm']),
"et_year_mm": float(readings['et_year_mm'])

}}
]
#============Sends data to localhost, database 'weather'

client = InfluxDBClient('127.0.0.1', 8086, 'root', 'root', database)

client.write_points(json_body)


#=========Downloads the Grafana panels========

grafanalink = 'http://192.168.1.141:3000/render/d-solo/J4QoPgZgk/weather?refresh=5s&orgId=1&'
panelstyle = '&theme=light&width=740&height=400&tz=UTC%2B10%3A00'
opener = urllib.request.build_opener()
opener.addheaders = [('Authorization', str(grafanaauth))]
urllib.request.install_opener(opener)

#=====Download the last 1 day panels======

urllib.request.urlretrieve(grafanalink + 'panelId=2' + panelstyle, webloc + 'temp.png')
urllib.request.urlretrieve(grafanalink + 'panelId=6' + panelstyle, webloc + 'wind.png')
urllib.request.urlretrieve(grafanalink + 'panelId=8' + panelstyle, webloc + 'solar.png')
urllib.request.urlretrieve(grafanalink + 'panelId=13' + panelstyle, webloc + 'rain.png')
urllib.request.urlretrieve(grafanalink + 'panelId=4' + panelstyle, webloc + 'pressure.png')
urllib.request.urlretrieve(grafanalink + 'panelId=11' + panelstyle, webloc + 'humidity.png')

#=====Download the last 7 day panels======

grafanalink = 'http://192.168.1.141:3000/render/d-solo/J4QoPgZgk/weather?refresh=5s&orgId=1&&from=now-7d&to=now&'
urllib.request.urlretrieve(grafanalink + 'panelId=2' + panelstyle, webloc + '7-temp.png')
urllib.request.urlretrieve(grafanalink + 'panelId=6' + panelstyle, webloc + '7-wind.png')
urllib.request.urlretrieve(grafanalink + 'panelId=8' + panelstyle, webloc + '7-solar.png')
urllib.request.urlretrieve(grafanalink + 'panelId=13' + panelstyle, webloc + '7-rain.png')
urllib.request.urlretrieve(grafanalink + 'panelId=4' + panelstyle, webloc + '7-pressure.png')
urllib.request.urlretrieve(grafanalink + 'panelId=11' + panelstyle, webloc + '7-humidity.png')



#========== Make the web page =============
webout = open(webloc + 'index.html','w')
webout.write('<html><head><title>Weather Bulletin</title><link rel="stylesheet" type="text/css" href="weather.css">\n')
webout.write('<link rel="apple-touch-icon-precomposed" sizes="57x57" href="images/apple-touch-icon-57x57.png" />\n')
webout.write('<link rel="apple-touch-icon-precomposed" sizes="114x114" href="images/apple-touch-icon-114x114.png" />\n')
webout.write('<link rel="apple-touch-icon-precomposed" sizes="72x72" href="images/apple-touch-icon-72x72.png" />\n')
webout.write('<link rel="apple-touch-icon-precomposed" sizes="144x144" href="images/apple-touch-icon-144x144.png" />\n')
webout.write('<link rel="apple-touch-icon-precomposed" sizes="60x60" href="images/apple-touch-icon-60x60.png" />\n')
webout.write('<link rel="apple-touch-icon-precomposed" sizes="120x120" href="images/apple-touch-icon-120x120.png" />\n')
webout.write('<link rel="apple-touch-icon-precomposed" sizes="76x76" href="images/apple-touch-icon-76x76.png" />\n')
webout.write('<link rel="apple-touch-icon-precomposed" sizes="152x152" href="images/apple-touch-icon-152x152.png" />\n')
webout.write('<link rel="icon" type="image/png" href="images/favicon-196x196.png" sizes="196x196" />\n')
webout.write('<link rel="icon" type="image/png" href="images/favicon-96x96.png" sizes="96x96" />\n')
webout.write('<link rel="icon" type="image/png" href="images/favicon-32x32.png" sizes="32x32" />\n')
webout.write('<link rel="icon" type="image/png" href="images/favicon-16x16.png" sizes="16x16" />\n')
webout.write('<link rel="icon" type="image/png" href="images/favicon-128.png" sizes="128x128" />\n')
webout.write('<meta http-equiv="refresh" content="120">\n')
webout.write('<meta name="application-name" content="&nbsp;"/>\n')
webout.write('<meta name="msapplication-TileColor" content="#FFFFFF" />\n')
webout.write('<meta name="msapplication-TileImage" content="mstile-144x144.png" />\n')
webout.write('<meta name="msapplication-square70x70logo" content="mstile-70x70.png" />\n')
webout.write('<meta name="msapplication-square150x150logo" content="mstile-150x150.png" />\n')
webout.write('<meta name="msapplication-wide310x150logo" content="mstile-310x150.png" />\n')
webout.write('<meta name="msapplication-square310x310logo" content="mstile-310x310.png" />\n')
webout.write('</head>\n')
webout.write('<body><h1>Current Conditions</h1>\n')
webout.write('<br>' + str(readings['observation_time']))
webout.write('<br><br><table border=0 cellpadding=3 cellspacing=3>\n')
webout.write('<tr><th colspan=6>Outside</th></tr>\n')
webout.write('<tr><th>Reading</th><th>Current</th><th id="thmax">Day High</th><th id="thmax">High Time</th><th id="thmin">Day Low</th><th id="thmin">Low Time</th></tr>\n')
webout.write('<tbody id="main"><tr><td>Temp</td><td>' + str(readings['temp_c']) + '&deg;C</td><td id="max">' + str(readings['temp_day_high_c']) + '&deg;C</td><td id="max">' + str(readings['temp_day_high_time']) + '</td><td id="min">' + str(readings['temp_day_low_c']) + '&deg;C</td><td id="min">' + str(readings['temp_day_low_time']) + '</td></tr>\n')
webout.write('<tr><td>Humidity</td><td>' + str(readings['relative_humidity']) + '%</td><td id="max">' + str(readings['relative_humidity_day_high']) + '%</td><td id="max">' + str(readings['relative_humidity_day_high_time']) + '</td><td id="min">' + str(readings['relative_humidity_day_low']) + '%</td><td id="min">' + str(readings['relative_humidity_day_low_time'])+ '</td></tr></tbody>\n')

if 'wind_day_high_kph' in readings:
  webout.write('<tbody id="wind"><tr><td>Wind Speed</td><td>' + str(readings['wind_kph']) + 'km/h</td><td id="max">' + str(readings['wind_day_high_kph']) + 'km/h</td><td id="max">' + str(readings['wind_day_high_time']) + '</td></tr>\n')
else: 
  webout.write('<tbody id="wind"><tr><td>Wind Speed</td><td>' + str(readings['wind_kph']) + 'km/h</td><td>0.0km/h</td><td>---</td></tr>\n')
webout.write('<tr><td>Wind Direction</td><td>' + str(readings['wind_degrees']) + '&deg;</td><td colspan=2>' + str(readings['wind_dir']) + '</td></tr>\n')
webout.write('<tr><td>Wind Gust</td><td>' + str(readings['wind_ten_min_gust_kph']) + ' km/h</td></tr></tbody>\n')

webout.write('<tbody id="rain"><tr><td>Rain</td><td>' + str(readings['rain_day_mm']) + 'mm</td></tr>\n')

if readings['rain_rate_day_high_mm_per_hr'] == 0.0: 
  webout.write('<tr><td>Rain Rate</td><td>' + str(readings['rain_rate_mm_per_hr']) + 'mm/h</td><td id="max">' + str(readings['rain_rate_day_high_mm_per_hr']) + 'mm/h</td><td id="max">---</td></tr></tbody>\n')
else:
  webout.write('<tr><td>Rain Rate</td><td>' + str(readings['rain_rate_mm_per_hr']) + 'mm/h</td><td id="max">' + str(readings['rain_rate_day_high_mm_per_hr']) + 'mm/h</td><td id="max">' + str(readings['rain_rate_day_high_time']) + '</td></tr></tbody>\n')

webout.write('<tbody id="solar"><tr><td>Solar Radiation</td><td>' + str(readings['solar_radiation']) + 'W/m<sup>2</sup></td><td id="max">' + str(readings['solar_radiation_day_high']) + 'W/m<sup>2</sup></td><td id="max">' + str(readings['solar_radiation_day_high_time']) + '</td></tr></tbody>\n')
webout.write('<tbody id="baro"><tr><td>Barometer</td><td>' + str(readings['pressure_mb']) + ' mb</td><td colspan=2>' + str(readings['pressure_tendency_string']) + '</td></tr></tbody>\n')

webout.write('<tr><th colspan=6>Inside</th></tr>\n')
webout.write('<tr><th>Reading</th><th>Current</th><th id="thmax">Day High</th><th id="thmax">High Time</th><th id="thmin">Day Low</th><th id="thmin">Low Time</th></tr>\n')
webout.write('<tbody id="main"><tr><td>Temp</td><td>' + str(readings['temp_in_c']) + '&deg;C</td><td id="max">' + str(readings['temp_in_day_high_c']) + '&deg;C</td><td id="max">' + str(readings['temp_in_day_high_time']) + '</td><td id="min">' + str(readings['temp_in_day_low_c']) + '&deg;C</td><td id="min">' + str(readings['temp_in_day_low_time']) + '</td></tr>\n')
webout.write('<tr><td>Humidity</td><td>' + str(readings['relative_humidity_in']) + '%</td><td id="max">' + str(readings['relative_humidity_in_day_high']) + '%</td><td id="max">' + str(readings['relative_humidity_in_day_high_time']) + '</td><td id="min">' + str(readings['relative_humidity_in_day_low']) + '%</td><td id="min">' + str(readings['relative_humidity_in_day_low_time'])+ '</td></tr></tbody>\n')
webout.write('</table>\n')

webout.write('<p><a href="index7.html">7 Day charts</a><p>\n')

webout.write('<img src="temp.png">\n')
webout.write('<img src="wind.png">\n')
webout.write('<img src="solar.png">\n')
webout.write('<img src="rain.png">\n')
webout.write('<img src="humidity.png">\n')
webout.write('<img src="pressure.png">\n')


webout.write('</body></html>')
webout.close

#====== Make 7 day webpage ======

webout = open(webloc + 'index7.html','w')
webout.write('<html><head><title>Weather Bulletin</title><link rel="stylesheet" type="text/css" href="weather.css">\n')
webout.write('<link rel="apple-touch-icon-precomposed" sizes="57x57" href="images/apple-touch-icon-57x57.png" />\n')
webout.write('<link rel="apple-touch-icon-precomposed" sizes="114x114" href="images/apple-touch-icon-114x114.png" />\n')
webout.write('<link rel="apple-touch-icon-precomposed" sizes="72x72" href="images/apple-touch-icon-72x72.png" />\n')
webout.write('<link rel="apple-touch-icon-precomposed" sizes="144x144" href="images/apple-touch-icon-144x144.png" />\n')
webout.write('<link rel="apple-touch-icon-precomposed" sizes="60x60" href="images/apple-touch-icon-60x60.png" />\n')
webout.write('<link rel="apple-touch-icon-precomposed" sizes="120x120" href="images/apple-touch-icon-120x120.png" />\n')
webout.write('<link rel="apple-touch-icon-precomposed" sizes="76x76" href="images/apple-touch-icon-76x76.png" />\n')
webout.write('<link rel="apple-touch-icon-precomposed" sizes="152x152" href="images/apple-touch-icon-152x152.png" />\n')
webout.write('<link rel="icon" type="image/png" href="images/favicon-196x196.png" sizes="196x196" />\n')
webout.write('<link rel="icon" type="image/png" href="images/favicon-96x96.png" sizes="96x96" />\n')
webout.write('<link rel="icon" type="image/png" href="images/favicon-32x32.png" sizes="32x32" />\n')
webout.write('<link rel="icon" type="image/png" href="images/favicon-16x16.png" sizes="16x16" />\n')
webout.write('<link rel="icon" type="image/png" href="images/favicon-128.png" sizes="128x128" />\n')
webout.write('<meta http-equiv="refresh" content="120">\n')
webout.write('<meta name="application-name" content="&nbsp;"/>\n')
webout.write('<meta name="msapplication-TileColor" content="#FFFFFF" />\n')
webout.write('<meta name="msapplication-TileImage" content="mstile-144x144.png" />\n')
webout.write('<meta name="msapplication-square70x70logo" content="mstile-70x70.png" />\n')
webout.write('<meta name="msapplication-square150x150logo" content="mstile-150x150.png" />\n')
webout.write('<meta name="msapplication-wide310x150logo" content="mstile-310x150.png" />\n')
webout.write('<meta name="msapplication-square310x310logo" content="mstile-310x310.png" />\n')
webout.write('</head>\n')
webout.write('<body><h1>Current Conditions</h1>\n')
webout.write('<br>' + str(readings['observation_time']))
webout.write('<br><br><table border=0 cellpadding=3 cellspacing=3>\n')
webout.write('<tr><th colspan=6>Outside</th></tr>\n')
webout.write('<tr><th>Reading</th><th>Current</th><th id="thmax">Day High</th><th id="thmax">High Time</th><th id="thmin">Day Low</th><th id="thmin">Low Time</th></tr>\n')
webout.write('<tbody id="main"><tr><td>Temp</td><td>' + str(readings['temp_c']) + '&deg;C</td><td id="max">' + str(readings['temp_day_high_c']) + '&deg;C</td><td id="max">' + str(readings['temp_day_high_time']) + '</td><td id="min">' + str(readings['temp_day_low_c']) + '&deg;C</td><td id="min">' + str(readings['temp_day_low_time']) + '</td></tr>\n')
webout.write('<tr><td>Humidity</td><td>' + str(readings['relative_humidity']) + '%</td><td id="max">' + str(readings['relative_humidity_day_high']) + '%</td><td id="max">' + str(readings['relative_humidity_day_high_time']) + '</td><td id="min">' + str(readings['relative_humidity_day_low']) + '%</td><td id="min">' + str(readings['relative_humidity_day_low_time'])+ '</td></tr></tbody>\n')

if 'wind_day_high_kph' in readings:
  webout.write('<tbody id="wind"><tr><td>Wind Speed</td><td>' + str(readings['wind_kph']) + 'km/h</td><td id="max">' + str(readings['wind_day_high_kph']) + 'km/h</td><td id="max">' + str(readings['wind_day_high_time']) + '</td></tr>\n')
else: 
  webout.write('<tbody id="wind"><tr><td>Wind Speed</td><td>' + str(readings['wind_kph']) + 'km/h</td><td>0.0km/h</td><td>---</td></tr>\n')
webout.write('<tr><td>Wind Direction</td><td>' + str(readings['wind_degrees']) + '&deg;</td><td colspan=2>' + str(readings['wind_dir']) + '</td></tr>\n')
webout.write('<tr><td>Wind Gust</td><td>' + str(readings['wind_ten_min_gust_kph']) + ' km/h</td></tr></tbody>\n')

webout.write('<tbody id="rain"><tr><td>Rain</td><td>' + str(readings['rain_day_mm']) + 'mm</td></tr>\n')

if readings['rain_rate_day_high_mm_per_hr'] == 0.0: 
  webout.write('<tr><td>Rain Rate</td><td>' + str(readings['rain_rate_mm_per_hr']) + 'mm/h</td><td id="max">' + str(readings['rain_rate_day_high_mm_per_hr']) + 'mm/h</td><td id="max">---</td></tr></tbody>\n')
else:
  webout.write('<tr><td>Rain Rate</td><td>' + str(readings['rain_rate_mm_per_hr']) + 'mm/h</td><td id="max">' + str(readings['rain_rate_day_high_mm_per_hr']) + 'mm/h</td><td id="max">' + str(readings['rain_rate_day_high_time']) + '</td></tr></tbody>\n')

webout.write('<tbody id="solar"><tr><td>Solar Radiation</td><td>' + str(readings['solar_radiation']) + 'W/m<sup>2</sup></td><td id="max">' + str(readings['solar_radiation_day_high']) + 'W/m<sup>2</sup></td><td id="max">' + str(readings['solar_radiation_day_high_time']) + '</td></tr></tbody>\n')
webout.write('<tbody id="baro"><tr><td>Barometer</td><td>' + str(readings['pressure_mb']) + ' mb</td><td colspan=2>' + str(readings['pressure_tendency_string']) + '</td></tr></tbody>\n')

webout.write('<tr><th colspan=6>Inside</th></tr>\n')
webout.write('<tr><th>Reading</th><th>Current</th><th id="thmax">Day High</th><th id="thmax">High Time</th><th id="thmin">Day Low</th><th id="thmin">Low Time</th></tr>\n')
webout.write('<tbody id="main"><tr><td>Temp</td><td>' + str(readings['temp_in_c']) + '&deg;C</td><td id="max">' + str(readings['temp_in_day_high_c']) + '&deg;C</td><td id="max">' + str(readings['temp_in_day_high_time']) + '</td><td id="min">' + str(readings['temp_in_day_low_c']) + '&deg;C</td><td id="min">' + str(readings['temp_in_day_low_time']) + '</td></tr>\n')
webout.write('<tr><td>Humidity</td><td>' + str(readings['relative_humidity_in']) + '%</td><td id="max">' + str(readings['relative_humidity_in_day_high']) + '%</td><td id="max">' + str(readings['relative_humidity_in_day_high_time']) + '</td><td id="min">' + str(readings['relative_humidity_in_day_low']) + '%</td><td id="min">' + str(readings['relative_humidity_in_day_low_time'])+ '</td></tr></tbody>\n')
webout.write('</table>\n')

webout.write('<p><a href="index.html">24 Hour charts</a><p>\n')

webout.write('<img src="7-temp.png">\n')
webout.write('<img src="7-wind.png">\n')
webout.write('<img src="7-solar.png">\n')
webout.write('<img src="7-rain.png">\n')
webout.write('<img src="7-humidity.png">\n')
webout.write('<img src="7-pressure.png">\n')


webout.write('</body></html>')
webout.close


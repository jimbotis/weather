# weather
A script to read data from the weatherlink 2.0 API, write the data to InfluxDB and present it as a webpage.  This includes downloading panels from Grafana to present in the webpage
This script requires additional files called: 
xmllink.txt that has nothing but the link to an xml file provided by Weatherlink.
grafanaauth.txt that has the Grafana API key in the format "Bearer <api key>"

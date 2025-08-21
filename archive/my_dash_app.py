import dash
from dash import html, dcc
import dash_leaflet as dl
import json
from threading import Timer
import webbrowser

from dash.dependencies import Input, Output

# Load your GeoJSON data
with open("benches.geojson", "r") as f:
    benches_geojson = json.load(f)

# Initialize Dash app
app = dash.Dash(__name__)

# Layout with map and GeoJSON overlay
app.layout = html.Div([
    dcc.Checklist(
        options=[{"label": "Within 100m of a public toilet", "value": "toilet_100"},],
        value=[], #values starts out empty and becomes "[toilet_100]" when the box is checked
        id="toilet_100-filter"
    ),
    dcc.Checklist(
        options=[{"label": "Within 100m of a shop", "value": "shops_100"},],
        value=[],
        id="shops_100-filter"
    ),
        dcc.Checklist(
        options=[{"label": "At least 10m from a big street", "value": "streets_10"},],
        value=[],
        id="streets_10-filter"
    ),
    dl.Map(center=[51.2277, 6.7735], zoom=13, children=[
        dl.TileLayer(
            url="https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png",
            attribution='&copy; <a href="https://carto.com/">CARTO</a>'
        ),  # base map
        dl.GeoJSON(data=benches_geojson, id="bench-layer")
    ], style={'width': '100%', 'height': '90vh'}),
])

@app.callback(
    Output("bench-layer", "data"),
    Input("toilet_100-filter", "value"), #“Watch the component whose id="checkbox". Whenever its value property changes, call the callback function, and pass in the new value as an argument.”
    Input("shops_100-filter", "value"),
    Input("streets_10-filter", "value")
)
def filter_benches(toilet_val, shops_val,streets_val):
    features = benches_geojson["features"] #grab the list of benches from the GeoJSON file

    if "toilet_100" in toilet_val:
        features = [f for f in features if f["properties"].get("toilet_100") is True] #go through the features and keep the ones close to a toilet
    
    if "shops_100" in shops_val:
        features = [f for f in features if f["properties"].get("shops_100") is True]

    if "streets_10" in streets_val:
        features = [f for f in features if f ["properties"].get("streets_10") is True]

    return {
        **benches_geojson,
        "features": features
    }
# this stacks because, if you had already checked the toilet filter, that filtered list is being filtered again after checking another box!

def open_browser():
    webbrowser.open("http://127.0.0.1:8050/")

if __name__ == "__main__":
    Timer(1, open_browser).start()
    app.run()

# how the heck does this code work? find out before messing with viewport size, more filters, nicer display options et cetera
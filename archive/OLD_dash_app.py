import dash
from dash import html, dcc, no_update
import dash_leaflet as dl
import json
from threading import Timer
import webbrowser

from dash.dependencies import Input, Output

# Load your GeoJSON data
with open("Düsseldorf_benches.geojson", "r") as f:
    benches_geojson = json.load(f)

def create_bench_marker(feat): #takes each feature from the GeoJSON file as argument
    lon, lat = feat["geometry"]["coordinates"][0], feat["geometry"]["coordinates"][1]

    #fetch all distances and round them for the tooltip
    toilet_dist = feat["properties"]["toilet_distance"]
    shop_dist = feat["properties"]["shop_distance"]
    street_dist = feat["properties"]["street_distance"]

    nichtkiffen_text = "Kiffen nicht erlaubt"
    if feat["properties"]["nichtkiffen_distance"] > 100:
        nichtkiffen_text = "Kiffen erlaubt"

    
    nav_url = f"https://www.google.com/maps/dir/?api=1&destination={lat},{lon}"

    return dl.Marker(
        position=(lat, lon),
        children=[
            dl.Popup(
                [html.P(f"{toilet_dist:.0f} m zur nächsten Toilette"),
                 html.P(f"{shop_dist:.0f} m zum nächsten Laden"),
                 html.P(f"{street_dist:.0f} m zur nächsten großen Straße"),
                 html.P(nichtkiffen_text),
                 html.A("Mit Google Maps hierhin navigieren.", href=nav_url, target="_blank")] #makes it an <a> </a> thing?
            )]
        )

# Initialize Dash app
app = dash.Dash(__name__)

# Layout with map and GeoJSON overlay
app.layout = html.Div([
    
    html.Div(id="control-panel", children=[
        html.Label("Distance to Toilet (m)", htmlFor="toilet_slider"),
        dcc.RangeSlider(
            min=0, max=1000, step=10, value=[0,200], marks=None, tooltip={"placement": "bottom", "always_visible": True},
            id="toilet_slider",
            updatemode='mouseup' #only updates when the user stops clicking, avoiding redrawing constantly
            #marks=None,
            #tooltip={"placement": "bottom", "always_visible": True}
        ),
        html.Label("Distance to shop (m)", htmlFor="shop_slider"),
        dcc.RangeSlider(
            min=0, max=1000, step=10, value=[0,300], marks=None, tooltip={"placement": "bottom", "always_visible": True},
            id="shop_slider",
            updatemode='mouseup'
        ),
        html.Label("Distance to big streets (m)", htmlFor="street_slider"),
        dcc.RangeSlider(
            min=0, max=1000, step=10, value=[0,1000], marks=None, tooltip={"placement": "bottom", "always_visible": True},
            id="street_slider",
            updatemode='mouseup'
        ),
        dcc.Checklist(
            options=[{"label": "Kiffen erlaubt", "value": "kiffen"}],
            value=[],
            id="nichtkiffen_checkbox"
            )
        ]),

    dl.Map(center=[51.2277, 6.7735], zoom=13, children=[
        dl.TileLayer(
            url="https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png",
            attribution='&copy; <a href="https://carto.com/">CARTO</a>' #adds a little link text in the bottom right
        ),  # base map
        dl.LayerGroup(id="bench-layer")
        #*[create_bench_marker(b) for b in benches_geojson["features"]]
        #dl.GeoJSON(data=benches_geojson, id="bench-layer") #, superClusterOptions={"maxZoom": 4}
    ], style={'width': '100%', 'height': '100vh'}),
])

@app.callback(
    Output("bench-layer", "children"),
    Input("toilet_slider", "value"),
    Input("shop_slider", "value"),
    Input("street_slider", "value"),
    Input("nichtkiffen_checkbox", "value")
)
def filter_benches(toilet_range: list, shop_range: list, street_range: list, kiffen: list):
    features = benches_geojson["features"] #grab the list of benches from the GeoJSON file

    print("toilet_range:", toilet_range)
    print("shop_range:", shop_range)
    print("street_range:", street_range)
    print("nichtkiffen_checkbox:", kiffen)

    filtered = [f for f in features 
                if f["properties"].get("toilet_distance") is not None and
                    toilet_range[0] <= f["properties"]["toilet_distance"] <= toilet_range[1]
                and f["properties"].get("shop_distance") is not None and
                    shop_range[0] <= f["properties"]["shop_distance"] <= shop_range[1]
                and f["properties"].get("street_distance") is not None and
                    street_range[0] <= f["properties"]["street_distance"] <= street_range[1]  
                and (100 < f["properties"]["nichtkiffen_distance"] or ("kiffen" not in kiffen))
                ]
    print(f"Number of filtered benches: {len(filtered)}")

    return [create_bench_marker(f) for f in filtered] #this list might contain the children for the output?
# this stacks because, if you had already checked the toilet filter, that filtered list is being filtered again after checking another box!

def open_browser():
    webbrowser.open("http://127.0.0.1:8050/")

if __name__ == "__main__":
    Timer(1, open_browser).start()
    app.run()
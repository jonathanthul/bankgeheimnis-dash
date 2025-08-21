import dash
import dash_leaflet as dl
from dash import html

app = dash.Dash(__name__)

icon = dl.Icon(
    iconUrl="bench.png",
    iconSize=[25, 41],
    iconAnchor=[12, 41]
)

app.layout = html.Div([
    dl.Map(center=[51.2277, 6.7735], zoom=13, children=[
        dl.TileLayer(),
        dl.Marker(position=[51.2277, 6.7735], icon=icon)
    ], style={'width': '100%', 'height': '100vh'})
])

if __name__ == "__main__":
    app.run_server(debug=True)

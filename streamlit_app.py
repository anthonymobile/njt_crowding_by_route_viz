# -*- coding: utf-8 -*-

from cProfile import label
from datetime import datetime
from tokenize import Ignore
import altair as alt
import numpy as np
import pandas as pd
import pydeck as pdk
import streamlit as st

from NJTransitAPI import *

#TODO: pass as kwarg from outside
route = "119"

# SETTING PAGE CONFIG TO WIDE MODE AND ADDING A TITLE AND FAVICON
st.set_page_config(layout="wide", page_title="CROWDR: Visualizing Poor Service on NJTransit", page_icon=":bus:")

class Bundle():
    def __init__(self, stoplist, data):
        self.stoplist = stoplist
        self.data = data


# get route geometry and pack into a flat list (e.g. 2 services in 2 directions = 4 list items)
def get_paths(route):
    data, fetch_timestamp = get_xml_data('nj', 'route_points', route=route)
    geometry = parse_xml_getRoutePoints(data)
    
    # unpack the first list of Routes
    route = geometry[0]
    
    # # diagnostic
    # st.write(type(route))
    # for path in route.paths:
    #     st.write(type(path))
    #     st.write(path.get_stoplist())
        
    # return a list of Route.Path objects (which we can use get_stoplist(), or iterate over their Route.Path.points list)
    return route.paths
        


# LOAD DATA ONCE
# @st.experimental_singleton
def load_data():
    
    cols = [
        "timestamp",
        "route",
        "stop_id", 
        "destination",
        "headsign",
        "vehicle_id", 
        "eta_min", 
        "eta_time", 
        "crowding"]
    
    datatypes = {
        "timestamp": str,
        "route": str,
        "stop_id": str, 
        "destination": str,
        "headsign": str,
        "vehicle_id": str, 
        "eta_min": str,
        "eta_time": str,
        "crowding": str
    }
    
    data = pd.read_csv(
        f"https://njtransit-crowding-data.s3.amazonaws.com/njt-crowding-route-{route}.csv",
        names= cols,
        dtype=datatypes,
        on_bad_lines='skip',
        # parse_dates=["timestamp"]
    )
    
    # drop those without ETA_min
    data.dropna(subset=['eta_min'])
    
    # drop no crowding data; encode crowding
    data.drop(data.loc[data['crowding']=='NO DATA'].index,inplace=True)
    
    # drop non-nyc destinations (119 only)
    data.drop(data.loc[data['destination']=='BAYONNE'].index,inplace=True)
    
    #drop duplicate rows
    data.drop_duplicates(
        subset=['vehicle_id','eta_time'], 
        keep=False
        )

    # # recode data    
    # data['crowding_int'] = data['crowding'].replace({'LIGHT': 1, 'MEDIUM': 2, 'HEAVY': 3}).astype(int)

    paths = get_paths(route)
    
    # fix timestamps
    data['timestamp'] = pd.to_datetime(data['timestamp']).dt.tz_convert('America/New_York')

    # create path, data bundles for chart making
    
    bundles = []
    
    for path in paths:

        # SECOND get_stoplist_df
        stoplist = path.get_stoplist_df()
        
        # FIRST filter fetched data based on ? path id? stoplist ? d from stoplist?
        df = data.???
    
        # THIRD join them
        
        df = pd.merge(
            df,
            stoplist,
            on='stop_id',
            how='left'
            )
        
        # FOURTH pack them into a Bundle
        bundle = Bundle(stoplist, data)
        
        # FIFTH path that Bundle into a list
        bundles.append(bundle)
    
    return bundles


# FILTER DATA FOR A SPECIFIC HOUR, CACHE
@st.experimental_memo
def filterdata(df, hour_selected):
    return df[df["timestamp"].dt.hour == hour_selected]


# STREAMLIT APP LAYOUT

#######################################################
# GET THE DATA AND STOPLIST BUNDLES
bundles = load_data()

# LAYING OUT THE TOP SECTION OF THE APP
row1_1, row1_2 = st.columns((2, 3))

# SEE IF THERE'S A QUERY PARAM IN THE URL (e.g. ?service_hour=2)
# THIS ALLOWS YOU TO PASS A STATEFUL URL TO SOMEONE WITH A SPECIFIC HOUR SELECTED,
# E.G. https://share.streamlit.io/streamlit/demo-uber-nyc-pickups/main?service_hour=2
if not st.session_state.get("url_synced", False):
    try:
        service_hour = int(st.experimental_get_query_params()["service_hour"][0])
        st.session_state["service_hour"] = service_hour
        st.session_state["url_synced"] = True
    except KeyError:
        pass

# IF THE SLIDER CHANGES, UPDATE THE QUERY PARAM
def update_query_params():
    hour_selected = st.session_state["service_hour"]
    st.experimental_set_query_params(service_hour=hour_selected)

with row1_1:
    st.title("How Crowded is the 119?")
    st.subheader("An investigation of NJTransit bus service in Jersey City Heights")
    hour_selected = st.slider(
        "Select hour of service", 0, 23, key="service_hour", on_change=update_query_params
    )

with row1_2:
    
    #FIXME: len(bundles[0][0]?)
    l = len(data)
    
    st.write("""The 119 is one of the most important bus routes in The Heights, linking Central Avenue to New York City. But during rush hour, buses are often full by the time they reach Palisade Avenue, and bypass stranded passengers.""")

    st.write(f"""The charts below summarize {l} observations scraped from NJTransit apps since {data['timestamp'].min().date()} to illustrate how bus overcrowding is experienced by riders. """)
    
    st.write("""By sliding the slider on the left you can choose an hour of the day, and see how buses fill up as they approach this stop during different times of day.""")
    


#######################################################
# CROWDING BAR CHARTS 

for bundle in bundles:

    # FILTER DATA BY HOUR
    @st.experimental_memo
    def plotdata(df, hr):
        filtered = bundle.data[
            (df["timestamp"].dt.hour >= hr) & (df["timestamp"].dt.hour < (hr + 1))
        ]

        # https://stackoverflow.com/questions/50465860/groupby-and-count-on-dataframe-having-two-categorical-variables
        array = filtered.groupby(['stop_name','crowding']).size().reset_index(name='count')
            
        return array
        # return pd.DataFrame({"eta_min": array.index, "crowding": array})

    plot_data = plotdata(bundle.data, hour_selected)

    st.altair_chart(
        alt.Chart(plot_data)
        .mark_bar(
            size=30,
            cornerRadiusTopLeft=3,
            cornerRadiusTopRight=3
        )
        .encode(
            x=alt.X(
                "stop_name:N",
                title="",
                sort=list(bundle.stoplist['stop_name'])
                ),
            y=alt.Y("count:Q", title="Number of Buses Observed at This Stop", axis=alt.Axis(tickMinStep=1)),
            color=alt.Color(
                "crowding:N", sort=['LIGHT','MEDIUM','HEAVY']
                ),
            order=alt.Order(
                'crowding:N',sort='descending'
                )
        )
        .configure_mark(opacity=0.4, color="red"),
        use_container_width=True,
    )

    st.altair_chart(
        alt.Chart(plot_data)
        .mark_area()
        .encode(
            x=alt.X(
                "stop_name:N",
                title="",
                sort=list(bundle.stoplist['stop_name'])
                ),
            y=alt.Y("count:Q", title="Number of Buses Observed ", axis=alt.Axis(tickMinStep=1)),
            color=alt.Color(
                "crowding:N", sort=['LIGHT','MEDIUM','HEAVY']
                ),
            order=alt.Order(
                'crowding:N',sort='descending'
                )
        )
        .configure_mark(opacity=0.4, color="red"),
        use_container_width=True,
    )

# #######################################################
# # CROWDING HISTOGRAM


# # FILTER DATA BY HOUR
# @st.experimental_memo
# def plotdata(df, hr):
#     filtered = data[
#         (df["timestamp"].dt.hour >= hr) & (df["timestamp"].dt.hour < (hr + 1))
#     ]
#     filtered['crowding_int'] = filtered['crowding'].replace({'LIGHT': 1, 'MEDIUM': 2, 'HEAVY': 3}).astype(int)

#     array = filtered.groupby('stop_id')['crowding_int'].mean()
    
#     return pd.DataFrame({"stop_id": array.index, "average_crowding": array})

# plot_data = plotdata(data, hour_selected)


# st.write(
#     f"""**Average level of crowding, between {hour_selected}:00 and {(hour_selected + 1) % 24}:00**"""
# )


# st.altair_chart(
#     alt.Chart(plot_data)
#     .mark_area(
#         interpolate="natural",
#     )
#     .encode(
#         x=alt.X("stop_id:N", scale=alt.Scale(nice=False)),
#         y=alt.Y("average_crowding:Q", scale=alt.Scale(domain=[0, 3])),
#         tooltip=["stop_id", "average_crowding"],
#         # axis = alt.Axis(labels=['test label']) #substitute text tick mark labels?
#     
#     .configure_mark(opacity=0.2, color="red"),
#     use_container_width=True,
# )



# #######################################################
# # OBSERVATION HISTOGRAM

# # FILTER DATA BY HOUR
# @st.experimental_memo
# def histdata(df, hr):
#     filtered = data[
#         (df["timestamp"].dt.hour >= hr) & (df["timestamp"].dt.hour < (hr + 1))
#     ]
#     hist = np.histogram(filtered["eta_min"], bins=60, range=(0, 60))[0]
#     return pd.DataFrame({"eta_min": range(60), "observations": hist})


# chart_data = histdata(data, hour_selected)

# # LAYING OUT THE HISTOGRAM SECTION
# st.write(
#     f"""**Number of observed approaching buses at given ETA to Congress St & Webster Ave stop, between {hour_selected}:00 and {(hour_selected + 1) % 24}:00**"""
# )
# st.altair_chart(
#     alt.Chart(chart_data)
#     .mark_area(
#         interpolate="step-after",
#     )
#     .encode(
#         x=alt.X("eta_min:Q", scale=alt.Scale(nice=False)),
#         y=alt.Y("observations:Q"),
#         tooltip=["eta_min", "observations"],
#     )
#     .configure_mark(opacity=0.2, color="red"),
#     use_container_width=True,
# )










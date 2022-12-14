from datetime import datetime

import altair as alt
import streamlit as st
import os
import itertools
    
from LoadData import *

#TODO: pass as kwarg from outside
route = "119"

# https://stackoverflow.com/questions/4563272/how-to-convert-a-utc-datetime-to-a-local-datetime-using-only-standard-library
def get_localtime():
    server_time = datetime.utcnow()
    from zoneinfo import ZoneInfo
    utc = ZoneInfo('UTC')
    localtz = ZoneInfo('America/New_York')
    utctime = server_time.replace(tzinfo=utc)
    localtime = utctime.astimezone(localtz)
    return localtime

# SETTING PAGE CONFIG TO WIDE MODE AND ADDING A TITLE AND FAVICON
st.set_page_config(layout="wide", page_title="CROWDR: Visualizing Poor Service on NJTransit", page_icon=":bus:")


#######################################################
# GET THE DATA AND STOPLIST BUNDLES
bundles = load_data(route)

# FILTER DATA FOR A SPECIFIC HOUR, CACHE
@st.experimental_memo
def filterdata(df, hour_selected):
    return df[df["timestamp"].dt.hour == hour_selected]

# #TODO: select a time range
# @st.experimental_memo
# def filterdata(df, t0, t1):
#     return ...

#######################################################
# STREAMLIT APP LAYOUT
bundles = load_data(route)
# LAYING OUT THE TOP SECTION OF THE APP

col1, col2 = st.columns(2)


# SEE IF THERE'S A QUERY PARAM IN THE URL (e.g. ?service_hour=2)
# THIS ALLOWS YOU TO PASS A STATEFUL URL TO SOMEONE WITH A SPECIFIC HOUR SELECTED,
# E.G. https://share.streamlit.io/streamlit/demo-uber-nyc-pickups/main?service_hour=2
if not st.session_state.get("url_synced", False):
    try:
        service_hour = int(st.experimental_get_query_params()["service_hour"][0])
        st.session_state["service_hour"] = service_hour
        st.session_state["url_synced"] = True
    # OTHERWISE SET VIEW TO CURRENT HOUR
    except KeyError:
        st.session_state["service_hour"] = get_localtime().hour

# IF THE SLIDER CHANGES, UPDATE THE QUERY PARAM
def update_query_params():
    hour_selected = st.session_state["service_hour"]
    st.experimental_set_query_params(service_hour=hour_selected)

#TODO: select a time range    
# # IF THE SLIDER CHANGES, UPDATE THE QUERY PARAM
# def update_query_params():
#     t0 = st.session_state["t0"]
#     t1 = st.session_state["t1"]
#     st.experimental_set_query_params(service_hour=hour_selected)


with col1:
    st.title("How Crowded is the 119?")
    st.subheader("An investigation of NJTransit bus service in Jersey City Heights")

with col2:

    num_observations = list(itertools.accumulate([len(b.dataframe) for b in bundles]))[0]
    start_timestamp = bundles[0].dataframe['timestamp'].min().date().strftime('%B %d, %Y')
        
    st.write("""The 119 is one of the most important bus routes in The Heights, linking Central Avenue to New York City. But during rush hour, buses are often full by the time they reach Palisade Avenue, and bypass stranded passengers.""")

    st.write(f"""The charts below summarizes {num_observations:,}  observations scraped from NJTransit since {start_timestamp} to illustrate how bus overcrowding is experienced by riders. """)

    st.write("""By sliding the slider on the left you can choose an hour of the day, and see how buses fill up as they approach this stop during different times of day.""")

    hour_selected = st.slider(
        f"It's currently {get_localtime().strftime('%H:%M')}. Choose another hour to view.", 0, 23, key="service_hour", on_change=update_query_params
    )

#TODO: select a time range
# from datetime import time
# appointment = st.slider(
#     "Schedule your appointment:",
#     value=(time(11, 30), time(12, 45)))
# st.write("You're scheduled for:", appointment)

    

#######################################################
# CROWDING BAR CHARTS 

# FILTER DATA BY HOUR
@st.experimental_memo
def plotdata(df, hr):
    filtered = bundle.dataframe[
        (df["timestamp"].dt.hour >= hr) & (df["timestamp"].dt.hour < (hr + 1))
    ]

    array = filtered.groupby(['stop_name','crowding']).size().reset_index(name='count')

    return array

#######################################################
# NORMALIZED

# # ABSOLUTE
# st.header("How Crowded Are Buses?")

# reversed() because to NY tends to be 2nd
for bundle in reversed(bundles):
    
    # #TODO: for testing only, remove for production
    # if bundle.stoplist.iloc[0]['d'] == 'Bayonne':
    #     continue

    plot_data = plotdata(bundle.dataframe, hour_selected)
        
    st.subheader(f"To {bundle.stoplist.iloc[0]['d']}")
    st.write("This chart shows the number of percentage of buses observed at each stop by how crowded they are. This roughly corresponds to how likely you are to find a bus at that stop with that level of crowding during this time of day.")


    st.altair_chart(
        alt.Chart(plot_data)
        .transform_calculate(
            order="{'HEAVY':0, 'MEDIUM': 1, 'LIGHT': 2}[datum.crowding]"  
            )
        .mark_bar(
            size=10,
            cornerRadiusTopLeft=3,
            cornerRadiusTopRight=3,
        )
        .encode(
            x=alt.X(
                "stop_name:N",
                title="",
                sort=list(bundle.stoplist['stop_name'])
                ),
            y=alt.Y("count:Q", 
                    title="percent of buses",
                    stack="normalize",
                    axis=alt.Axis(format="p",
                                  )
                    ),
            color=alt.Color(
                "crowding:N", sort=['LIGHT','MEDIUM','HEAVY']
                ),
            order="order:O"
        )
        .configure_mark(opacity=0.7, color="red"),
        use_container_width=True,
    )

# gcp-receiver
Cloud-based receiver on GCP

See google doc [Cloud-based receiver on GCP](https://docs.google.com/document/d/1F-k4PVgspK_OX9KaKR1LuEugTwXeQbvugA7dqxMoYlk).

* This webservice app is implemented in Python and CherryPy.
* For development and test,
    * Run the app locally, so it is serving at the local URL http://localhost:8080.<br>
    Exercise POST handling by running the included python script.<br>
    Exercise GET handling (to review POST data) by browsing to the
    local URL, with query parameters.
    * "deploy" the app to GCP, so it is serving at the GCP-Project URL https://<project_address>.<br>
    Exercise POST handling by running the included python script.<br>
    Exercise GET handling (to review POST data) by browsing to the
    GCP-Project URL, with query parameters.
* For "production" use,
    1. in main-gcp.yaml, disable the GET query actions (to provide data privacy),
    2. "deploy" the app to GCP,
    3. provide the GCP-Project URL for use by the sender sw.

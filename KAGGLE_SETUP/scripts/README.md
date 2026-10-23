# KAGGLE_SETUP Scripts

Operational scripts for KEYSTONE Tier 0 GPU workers on Kaggle (Bible §24):
- `probe_hardware.py`: Hardware memory and GPU probe verifying host RAM headroom and calculating 27B model offload.
- `start_gateway.sh`: Shell script to establish tunnels and bridge ports 8000 and 8189 with the Keystone API.

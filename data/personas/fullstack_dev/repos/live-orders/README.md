# live-orders

source: synthetic · document: repo_readme · persona: fullstack_dev

Realtime rider location for delivery orders. Riders POST GPS pings; customers subscribe to their
order room over WebSockets.

- Node 20, Express, Socket.IO, Redis adapter (runs on 2+ instances)
- Drops pings that imply impossible speeds
- Customers reconnecting get the last known position immediately

Load tested with 500 simulated riders on a single small VPS.

// source: synthetic · persona: fullstack_dev · repo: live-orders
const express = require("express");
const { createServer } = require("http");
const { Server } = require("socket.io");
const { createAdapter } = require("@socket.io/redis-adapter");
const { pub, sub, redis } = require("./redis");

const app = express();
app.use(express.json());
const http = createServer(app);
const io = new Server(http, { adapter: createAdapter(pub, sub) });

app.post("/riders/:orderId/ping", async (req, res) => {
  const { lat, lng } = req.body;
  if (typeof lat !== "number" || typeof lng !== "number") return res.status(400).end();
  await redis.set(`order:${req.params.orderId}:pos`, JSON.stringify({ lat, lng }));
  io.to(req.params.orderId).emit("position", { lat, lng });
  res.status(204).end();
});

io.on("connection", async (socket) => {
  const orderId = socket.handshake.query.orderId;
  socket.join(orderId);
  const last = await redis.get(`order:${orderId}:pos`);
  if (last) socket.emit("position", JSON.parse(last));
});

http.listen(process.env.PORT || 3000);

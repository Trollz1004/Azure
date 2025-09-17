const express = require('express');
const path = require('path');
const axios = require('axios');
require('dotenv').config();

const app = express();
app.use(express.json());
app.use(express.static(path.join(__dirname)));

const API = process.env.API_BASE || 'http://127.0.0.1:8011';
const KEY = process.env.LOCAL_API_KEY || 'local-dev-key-123';

app.post('/agents/twin/execute', async (req, res) => {
  try {
    const r = await axios.post(`${API}/agents/twin/execute`, req.body, { headers:{'x-api-key': KEY}});
    res.status(r.status).send(r.data);
  } catch(e) { res.status(502).send(e.response?.data || {error:e.message}); }
});

['/fundraising/deploy','/agents/create','/business/integrate','/admin/automate'].forEach(p=>{
  app.all(p, async (req,res)=>{
    try{
      const r = await axios({url:`${API}${p}`, method:req.method, data:req.body, headers:{'x-api-key': KEY}});
      res.status(r.status).send(r.data);
    }catch(e){ res.status(502).send(e.response?.data || {error:e.message}); }
  });
});

app.get('/previews/stream', (req,res)=>{
  // simple pass-through to API SSE
  res.setHeader('Cache-Control','no-cache');
  res.setHeader('Content-Type','text/event-stream');
  res.setHeader('Connection','keep-alive');
  const http = require('http');
  const url = new URL(`${API.replace('http://','http://')}/previews/stream`);
  const proxy = http.request(url, {method:'GET', headers:{}}, (pr)=>{
    pr.on('data', chunk=> res.write(chunk));
    pr.on('end', ()=> res.end());
  });
  proxy.on('error', ()=> res.end());
  proxy.end();
});

const PORT = process.env.PORT || 8080;
app.listen(PORT, ()=> console.log(`Twin Boss Console http://localhost:${PORT}`));

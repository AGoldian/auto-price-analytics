import time, logging
from typing import List, Optional

import uvicorn, torch
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from transformers import AutoTokenizer, AutoModelForCausalLM

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("hf_server")

MODEL_NAME = "mediocredev/open-llama-3b-v2-instruct"
logger.info("Loading tokenizer %s …", MODEL_NAME)
tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME, use_fast=False)

device = "mps" if torch.backends.mps.is_available() else "cpu"
logger.info("Loading model %s on %s …", MODEL_NAME, device)
model = AutoModelForCausalLM.from_pretrained(
    MODEL_NAME,
    device_map="auto" if device != "cpu" else None,
    torch_dtype=torch.float16 if device != "cpu" else torch.float32,
)
model.eval()
logger.info("Model loaded successfully")

class Message(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    model: str
    messages: List[Message]
    temperature: Optional[float] = Field(0.0, ge=0.0, le=2.0)
    max_tokens:   Optional[int]   = Field(16,  ge=1)

class Choice(BaseModel):
    index: int
    message: Message
    finish_reason: str

class ChatResponse(BaseModel):
    id: str
    object: str = "chat.completion"
    created: int
    model: str
    choices: List[Choice]

app = FastAPI(title="HF Transformers Inference Server")

@app.post("/v1/chat/completions", response_model=ChatResponse)
def chat_completions(req: ChatRequest):
    if req.model != MODEL_NAME:
        logger.error("Requested model %s != served %s", req.model, MODEL_NAME)
        raise HTTPException(400, detail=f"Only model `{MODEL_NAME}` is served")
    systems = [m.content for m in req.messages if m.role == "system"]
    system = systems[0] if systems else ""
    parts = []
    if system:
        parts.append(f"<system>{system}</system>")
    for m in req.messages:
        if m.role == "system": continue
        parts.append(f"<{m.role}>{m.content}</{m.role}>")
    parts.append("<assistant>")
    prompt = "\n".join(parts) + " "

    logger.debug("Prompt:\n%s", prompt)

    inputs = tokenizer(prompt, return_tensors="pt")
    inputs = {k: v.to(model.device) for k,v in inputs.items()}

    gen_kwargs = {
        **inputs,
        "max_new_tokens": req.max_tokens or 16,
        "pad_token_id": tokenizer.eos_token_id,
    }
    do_sample = (req.temperature or 0.0) > 0.0
    gen_kwargs["do_sample"] = do_sample
    if do_sample:
        gen_kwargs["temperature"] = req.temperature

    logger.info(
        "Generating (do_sample=%s, max_new_tokens=%d%s)…",
        gen_kwargs["do_sample"],
        gen_kwargs["max_new_tokens"],
        f", temp={gen_kwargs.get('temperature')}" if do_sample else ""
    )

    try:
        out = model.generate(**gen_kwargs)
    except Exception as e:
        logger.exception("Generation error")
        raise HTTPException(500, detail="Generation failed")

    generated_ids = out[0][inputs["input_ids"].shape[-1] :]
    text = tokenizer.decode(generated_ids, skip_special_tokens=True).strip()

    answer = text.splitlines()[0]

    logger.info("Generated answer: %r", answer)

    choice = Choice(
        index=0,
        message=Message(role="assistant", content=answer),
        finish_reason="stop"
    )
    return ChatResponse(
        id=f"chatcmpl-{int(time.time())}",
        created=int(time.time()),
        model=MODEL_NAME,
        choices=[choice]
    )

if __name__ == "__main__":
    uvicorn.run("server_transformers:app", host="0.0.0.0", port=1234, log_level="info")

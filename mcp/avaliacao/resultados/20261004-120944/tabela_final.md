| grupo | métrica | o que mede | rag_primeiro | livre |
|---|---|---|---|---|
| 1. Ferramentas | ToolHit | % de perguntas em que foi chamada pelo menos uma ferramenta esperada | 0.808 | 0.577 |
| 1. Ferramentas | ToolRecall | ferramentas esperadas que foram chamadas | 0.808 | 0.577 |
| 1. Ferramentas | ToolPrecision | ferramentas escolhidas pelo LLM que eram esperadas ou permitidas | 0.857 | 0.759 |
| 1. Ferramentas | NumToolCalls | chamadas a ferramentas por pergunta (média) | 1.269 | 0.885 |
| 2. Argumentos | ArgsValidos | chamadas do LLM com argumentos válidos para o esquema da ferramenta | 1.000 | 1.000 |
| 2. Argumentos | ArgsAdequados | chamadas do LLM com argumentos adequados à pergunta (juiz) | 1.000 | 1.000 |
| 3. Servidor MCP | TesteCorreto | testes diretos: chamadas com o resultado certo | 1.000 | 1.000 |
| 3. Servidor MCP | TesteRespondeu | testes diretos: chamadas a que o servidor respondeu | 1.000 | 1.000 |
| 3. Servidor MCP | TaxaSucesso | chamadas MCP do agente sem erro | 1.000 | 0.885 |
| 3. Servidor MCP | LatenciaMedia | segundos por chamada MCP do agente | 0.024 | 0.335 |
| 4. Correção | Correctness | % de respostas pass (Ragas, face à resposta esperada) | 0.923 | 0.654 |
| 4. Correção | JudgeScore | LLM-as-Judge 0-10 (prompt dos slides) | 9.269 | 7.385 |
| 4. Correção | AnswerRelevancy | a resposta responde ao que foi perguntado | 0.844 | 0.789 |
| 4. Correção | BLEU | n-gramas em comum com a resposta esperada | 0.238 | 0.125 |
| 4. Correção | ROUGE-L | maior sequência de palavras em comum | 0.463 | 0.305 |
| 5. Fundamentação | Faithfulness | afirmações da resposta suportadas pelas saídas das ferramentas | 0.795 | 0.723 |
| 6. Falhas | selecao_ferramenta | o LLM não chamou a ferramenta esperada | 1.000 | 6.000 |
| 6. Falhas | ferramenta_falhou | uma chamada MCP devolveu erro (com argumentos bons) | 0.000 | 3.000 |
| 6. Falhas | geracao | chamou as ferramentas certas, sem erros, mas a resposta saiu errada | 1.000 | 0.000 |

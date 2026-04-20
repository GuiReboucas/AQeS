"""
╔══════════════════════════════════════════════════════════╗
║        TESTES UNITÁRIOS — CONVERSOR DE MOEDAS            ║
║  Execute com:  python -m pytest tests/ -v                ║
║            ou: python -m unittest discover tests/        ║
╚══════════════════════════════════════════════════════════╝

Organização dos testes:
  1. TestConverter          → lógica de conversão (cálculo)
  2. TestFormatarValor      → formatação de moeda na tela
  3. TestObterTaxas         → fallback offline vs. API online
  4. TestBuscarTaxasApi     → chamada HTTP à API externa
  5. TestValidacaoEntradas  → entradas inválidas do usuário
  6. TestHistorico          → registro de histórico da sessão
"""

import sys
import os
import unittest
from unittest.mock import patch, MagicMock
import json

# Garante que o módulo principal é encontrado mesmo rodando de subpasta
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import conversor_moedas as app

# ──────────────────────────────────────────────────────────
#  FIXTURES — dados reutilizados em vários testes
# ──────────────────────────────────────────────────────────

# Taxas com USD como base (mesmo formato do fallback do app)
TAXAS_USD_BASE = {
    "USD": 1.0000,
    "BRL": 5.7800,
    "EUR": 0.9250,
    "GBP": 0.7920,
    "JPY": 149.500,
    "CAD": 1.3640,
    "AUD": 1.5380,
    "CHF": 0.8960,
    "CNY": 7.2400,
    "ARS": 870.00,
    "MXN": 17.150,
    "CLP": 930.00,
    "COP": 3940.0,
    "PEN": 3.7500,
    "UYU": 39.500,
}

# Taxas com BRL como base (simulando a API retornando BRL como raiz)
def _taxas_base(moeda_base: str) -> dict:
    """Converte TAXAS_USD_BASE para qualquer base."""
    divisor = TAXAS_USD_BASE[moeda_base]
    return {m: v / divisor for m, v in TAXAS_USD_BASE.items()}


# ══════════════════════════════════════════════════════════
#  1. TESTES DE CONVERSÃO (lógica de cálculo)
# ══════════════════════════════════════════════════════════

class TestConverter(unittest.TestCase):
    """
    Testa a função converter() — núcleo do sistema.
    Cenários positivos e negativos com diversas moedas.
    """

    def setUp(self):
        """Taxas com USD como base, reutilizadas em todos os métodos."""
        self.taxas = _taxas_base("USD")

    # ── Cenários POSITIVOS ────────────────────────────────

    def test_usd_para_brl(self):
        """1 USD deve resultar na taxa BRL configurada."""
        resultado = app.converter(1.0, "USD", "BRL", self.taxas)
        self.assertAlmostEqual(resultado, 5.78, places=2)

    def test_brl_para_usd(self):
        """5.78 BRL deve valer aproximadamente 1 USD."""
        resultado = app.converter(5.78, "BRL", "USD", self.taxas)
        self.assertAlmostEqual(resultado, 1.0, places=2)

    def test_usd_para_eur(self):
        """1 USD deve resultar na taxa EUR configurada."""
        resultado = app.converter(1.0, "USD", "EUR", self.taxas)
        self.assertAlmostEqual(resultado, 0.925, places=3)

    def test_eur_para_gbp(self):
        """Conversão cruzada entre duas moedas não-USD."""
        resultado = app.converter(1.0, "EUR", "GBP", self.taxas)
        esperado = TAXAS_USD_BASE["GBP"] / TAXAS_USD_BASE["EUR"]
        self.assertAlmostEqual(resultado, esperado, places=4)

    def test_mesma_moeda_retorna_valor_igual(self):
        """Converter BRL para BRL deve retornar o mesmo valor."""
        resultado = app.converter(100.0, "BRL", "BRL", self.taxas)
        self.assertAlmostEqual(resultado, 100.0, places=2)

    def test_valor_zero(self):
        """Converter zero deve retornar zero em qualquer moeda."""
        resultado = app.converter(0.0, "USD", "BRL", self.taxas)
        self.assertEqual(resultado, 0.0)

    def test_valor_grande(self):
        """Valores grandes devem ser calculados sem overflow."""
        resultado = app.converter(1_000_000.0, "USD", "BRL", self.taxas)
        self.assertAlmostEqual(resultado, 5_780_000.0, places=0)

    def test_valor_fracionado(self):
        """Valores com muitas casas decimais devem manter precisão."""
        resultado = app.converter(0.01, "USD", "BRL", self.taxas)
        self.assertAlmostEqual(resultado, 0.0578, places=4)

    def test_precisao_minima_duas_casas(self):
        """Resultado deve ter precisão de ao menos duas casas decimais."""
        resultado = app.converter(1.0, "USD", "BRL", self.taxas)
        # Verifica que o resultado tem ao menos 2 casas significativas
        resultado_arredondado = round(resultado, 2)
        self.assertEqual(resultado_arredondado, 5.78)

    def test_conversao_invertida_consistente(self):
        """
        Converter A→B e depois B→A deve retornar valor próximo ao original.
        Testa a consistência matemática (ida e volta).
        """
        valor_original = 250.0
        ida  = app.converter(valor_original, "USD", "BRL", self.taxas)
        volta = app.converter(ida, "BRL", "USD", self.taxas)
        self.assertAlmostEqual(volta, valor_original, places=6)

    def test_usd_para_jpy(self):
        """Moedas sem casas decimais (JPY) devem funcionar corretamente."""
        resultado = app.converter(1.0, "USD", "JPY", self.taxas)
        self.assertAlmostEqual(resultado, 149.5, places=1)

    def test_multiplas_moedas_latam(self):
        """Testa conversões entre moedas latino-americanas."""
        pares = [("BRL", "ARS"), ("MXN", "CLP"), ("PEN", "COP"), ("UYU", "BRL")]
        for origem, destino in pares:
            with self.subTest(par=f"{origem}->{destino}"):
                resultado = app.converter(100.0, origem, destino, self.taxas)
                self.assertGreater(resultado, 0,
                    msg=f"Resultado deve ser positivo para {origem}->{destino}")

    # ── Cenários NEGATIVOS ────────────────────────────────

    def test_valor_negativo_retorna_negativo(self):
        """
        A função converter() aceita negativos matematicamente.
        A proteção contra negativos está na camada de entrada (ler_valor).
        """
        resultado = app.converter(-100.0, "USD", "BRL", self.taxas)
        self.assertLess(resultado, 0)

    def test_moeda_ausente_nas_taxas_lanca_keyerror(self):
        """Moeda não presente nas taxas deve lançar KeyError."""
        with self.assertRaises(KeyError):
            app.converter(100.0, "XYZ", "BRL", self.taxas)

    def test_divisao_por_taxa_zero_lanca_excecao(self):
        """Taxa zero na origem deve lançar ZeroDivisionError."""
        taxas_corrompidas = dict(self.taxas)
        taxas_corrompidas["USD"] = 0.0
        with self.assertRaises(ZeroDivisionError):
            app.converter(100.0, "USD", "BRL", taxas_corrompidas)


# ══════════════════════════════════════════════════════════
#  2. TESTES DE FORMATAÇÃO
# ══════════════════════════════════════════════════════════

class TestFormatarValor(unittest.TestCase):
    """
    Testa a função formatar_valor() — exibição para o usuário.
    """

    def test_brl_duas_casas_decimais(self):
        resultado = app.formatar_valor(1234.5, "BRL")
        self.assertIn("1,234.50", resultado)
        self.assertIn("R$", resultado)

    def test_usd_simbolo_correto(self):
        resultado = app.formatar_valor(99.99, "USD")
        self.assertIn("US$", resultado)
        self.assertIn("99.99", resultado)

    def test_eur_simbolo_correto(self):
        resultado = app.formatar_valor(50.0, "EUR")
        self.assertIn("€", resultado)

    def test_jpy_sem_casas_decimais(self):
        """Iene japonês não deve exibir casas decimais."""
        resultado = app.formatar_valor(1000.7, "JPY")
        self.assertIn("1,001", resultado)   # arredondado
        self.assertNotIn(".7", resultado)

    def test_valor_zero_formatado(self):
        resultado = app.formatar_valor(0.0, "USD")
        self.assertIn("0.00", resultado)

    def test_valor_grande_com_separador_milhar(self):
        resultado = app.formatar_valor(1_000_000.0, "BRL")
        self.assertIn("1,000,000.00", resultado)

    def test_moeda_desconhecida_nao_quebra(self):
        """Moeda sem símbolo cadastrado deve retornar string sem símbolo."""
        resultado = app.formatar_valor(10.0, "ZZZ")
        self.assertIn("10.00", resultado)


# ══════════════════════════════════════════════════════════
#  3. TESTES DE OBTENÇÃO DE TAXAS (API vs. fallback)
# ══════════════════════════════════════════════════════════

class TestObterTaxas(unittest.TestCase):
    """
    Testa obter_taxas() — decide se usa API ou fallback.
    Usa mock para não fazer chamadas reais à internet.
    """

    @patch("conversor_moedas.buscar_taxas_api")
    @patch("conversor_moedas.spinner")
    def test_usa_api_quando_disponivel(self, mock_spinner, mock_api):
        """Quando a API retorna dados, online=True e as taxas vêm dela."""
        mock_api.return_value = {m: v for m, v in TAXAS_USD_BASE.items()}
        taxas, online = app.obter_taxas("USD")
        self.assertTrue(online, "Deveria indicar que está online")
        self.assertIn("BRL", taxas)
        self.assertIn("EUR", taxas)

    @patch("conversor_moedas.buscar_taxas_api")
    @patch("conversor_moedas.spinner")
    def test_usa_fallback_quando_api_falha(self, mock_spinner, mock_api):
        """Quando API retorna None, online=False e taxas vêm do fallback."""
        mock_api.return_value = None
        taxas, online = app.obter_taxas("USD")
        self.assertFalse(online, "Deveria indicar modo offline")
        self.assertIn("BRL", taxas)

    @patch("conversor_moedas.buscar_taxas_api")
    @patch("conversor_moedas.spinner")
    def test_fallback_calcula_base_corretamente(self, mock_spinner, mock_api):
        """
        Offline com base BRL: taxa de BRL deve ser 1.0
        (a própria moeda sempre vale 1 em relação a si mesma).
        """
        mock_api.return_value = None
        taxas, _ = app.obter_taxas("BRL")
        self.assertAlmostEqual(taxas["BRL"], 1.0, places=6)

    @patch("conversor_moedas.buscar_taxas_api")
    @patch("conversor_moedas.spinner")
    def test_todas_moedas_presentes_no_fallback(self, mock_spinner, mock_api):
        """Fallback deve conter todas as moedas definidas em TAXAS_FALLBACK."""
        mock_api.return_value = None
        taxas, _ = app.obter_taxas("USD")
        for moeda in app.TAXAS_FALLBACK:
            self.assertIn(moeda, taxas,
                msg=f"Moeda {moeda} ausente nas taxas fallback")

    @patch("conversor_moedas.buscar_taxas_api")
    @patch("conversor_moedas.spinner")
    def test_taxas_sao_positivas(self, mock_spinner, mock_api):
        """Todas as taxas retornadas devem ser maiores que zero."""
        mock_api.return_value = None
        taxas, _ = app.obter_taxas("USD")
        for moeda, taxa in taxas.items():
            self.assertGreater(taxa, 0,
                msg=f"Taxa de {moeda} não pode ser zero ou negativa")


# ══════════════════════════════════════════════════════════
#  4. TESTES DA CHAMADA À API EXTERNA
# ══════════════════════════════════════════════════════════

class TestBuscarTaxasApi(unittest.TestCase):
    """
    Testa buscar_taxas_api() — chamada HTTP real (mockada).
    Verifica: resposta de sucesso, erro HTTP, timeout, chave inválida.
    """

    def _mock_response(self, data: dict):
        """Cria um objeto que simula urllib.request.urlopen."""
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(data).encode()
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        return mock_resp

    @patch("conversor_moedas.API_KEY", "chave-valida-123")
    @patch("urllib.request.urlopen")
    def test_retorna_taxas_em_sucesso(self, mock_urlopen):
        """Resposta válida da API deve retornar dicionário de taxas."""
        payload = {
            "result": "success",
            "conversion_rates": TAXAS_USD_BASE
        }
        mock_urlopen.return_value = self._mock_response(payload)
        taxas = app.buscar_taxas_api("USD")
        self.assertIsNotNone(taxas)
        self.assertIn("BRL", taxas)
        self.assertAlmostEqual(taxas["BRL"], 5.78, places=2)

    @patch("conversor_moedas.API_KEY", "chave-valida-123")
    @patch("urllib.request.urlopen")
    def test_retorna_none_em_erro_http(self, mock_urlopen):
        """Erro HTTP (404, 500…) deve retornar None, não lançar exceção."""
        import urllib.error
        mock_urlopen.side_effect = urllib.error.HTTPError(
            url="", code=401, msg="Unauthorized", hdrs=None, fp=None
        )
        resultado = app.buscar_taxas_api("USD")
        self.assertIsNone(resultado)

    @patch("conversor_moedas.API_KEY", "chave-valida-123")
    @patch("urllib.request.urlopen")
    def test_retorna_none_em_timeout(self, mock_urlopen):
        """Timeout de conexão deve retornar None silenciosamente."""
        import socket
        mock_urlopen.side_effect = socket.timeout("timed out")
        resultado = app.buscar_taxas_api("USD")
        self.assertIsNone(resultado)

    @patch("conversor_moedas.API_KEY", "chave-valida-123")
    @patch("urllib.request.urlopen")
    def test_retorna_none_quando_result_nao_success(self, mock_urlopen):
        """Resposta com result != 'success' deve retornar None."""
        payload = {"result": "error", "error-type": "invalid-key"}
        mock_urlopen.return_value = self._mock_response(payload)
        resultado = app.buscar_taxas_api("USD")
        self.assertIsNone(resultado)

    def test_retorna_none_sem_chave_configurada(self):
        """Sem API_KEY real configurada, deve retornar None imediatamente."""
        with patch("conversor_moedas.API_KEY", "SUA_CHAVE_AQUI"):
            resultado = app.buscar_taxas_api("USD")
            self.assertIsNone(resultado)


# ══════════════════════════════════════════════════════════
#  5. TESTES DE VALIDAÇÃO DE ENTRADAS
# ══════════════════════════════════════════════════════════

class TestValidacaoEntradas(unittest.TestCase):
    """
    Testa o comportamento da interface com entradas inválidas.
    Usa mock em input() para simular o que o usuário digitaria.
    """

    @patch("builtins.input", side_effect=["abc", "-50", "100"])
    @patch("conversor_moedas.msg_erro")
    def test_ler_valor_rejeita_texto(self, mock_erro, mock_input):
        """Texto não numérico deve exibir erro e pedir novamente."""
        resultado = app.ler_valor("Valor")
        mock_erro.assert_called()   # msg_erro foi chamado ao menos uma vez
        self.assertEqual(resultado, 100.0)

    @patch("builtins.input", side_effect=["-10", "-1", "50"])
    @patch("conversor_moedas.msg_erro")
    def test_ler_valor_rejeita_negativo(self, mock_erro, mock_input):
        """Valor negativo deve exibir erro e pedir novamente."""
        resultado = app.ler_valor("Valor")
        mock_erro.assert_called()
        self.assertEqual(resultado, 50.0)

    @patch("builtins.input", side_effect=["0"])
    @patch("conversor_moedas.msg_aviso")
    def test_ler_valor_aceita_zero_com_aviso(self, mock_aviso, mock_input):
        """Zero é aceito mas deve exibir aviso ao usuário."""
        resultado = app.ler_valor("Valor")
        self.assertEqual(resultado, 0.0)
        mock_aviso.assert_called()

    @patch("builtins.input", side_effect=["100,50"])
    def test_ler_valor_aceita_virgula_como_decimal(self, mock_input):
        """Vírgula como separador decimal deve ser aceita."""
        resultado = app.ler_valor("Valor")
        self.assertAlmostEqual(resultado, 100.50, places=2)

    @patch("builtins.input", side_effect=["XYZ", "ABC", "BRL"])
    @patch("conversor_moedas.msg_erro")
    def test_ler_moeda_rejeita_codigo_invalido(self, mock_erro, mock_input):
        """Código de moeda inexistente deve exibir erro e pedir novamente."""
        resultado = app.ler_moeda("Moeda")
        mock_erro.assert_called()
        self.assertEqual(resultado, "BRL")

    @patch("builtins.input", side_effect=["usd"])
    def test_ler_moeda_aceita_minusculas(self, mock_input):
        """Código em minúsculas deve ser aceito (normalizado para maiúsculas)."""
        resultado = app.ler_moeda("Moeda")
        self.assertEqual(resultado, "USD")

    @patch("builtins.input", side_effect=["  BRL  "])
    def test_ler_moeda_ignora_espacos(self, mock_input):
        """Espaços em branco ao redor do código devem ser ignorados."""
        resultado = app.ler_moeda("Moeda")
        self.assertEqual(resultado, "BRL")


# ══════════════════════════════════════════════════════════
#  6. TESTES DE HISTÓRICO DA SESSÃO
# ══════════════════════════════════════════════════════════

class TestHistorico(unittest.TestCase):
    """
    Testa o registro e exibição do histórico de conversões.
    """

    def setUp(self):
        """Limpa o histórico antes de cada teste."""
        app.historico.clear()

    def test_registrar_adiciona_entrada(self):
        """registrar_historico() deve adicionar um item ao histórico."""
        app.registrar_historico(100.0, "USD", "BRL", 578.0)
        self.assertEqual(len(app.historico), 1)

    def test_historico_contem_campos_corretos(self):
        """Entrada do histórico deve ter os campos 'hora', 'de' e 'para'."""
        app.registrar_historico(50.0, "EUR", "USD", 54.0)
        entrada = app.historico[0]
        self.assertIn("hora", entrada)
        self.assertIn("de", entrada)
        self.assertIn("para", entrada)

    def test_multiplas_conversoes_acumulam(self):
        """Várias conversões devem acumular no histórico."""
        app.registrar_historico(10.0, "USD", "BRL", 57.8)
        app.registrar_historico(20.0, "EUR", "GBP", 17.0)
        app.registrar_historico(30.0, "BRL", "JPY", 775.0)
        self.assertEqual(len(app.historico), 3)

    @patch("builtins.print")
    def test_exibir_historico_vazio_mostra_aviso(self, mock_print):
        """Histórico vazio deve exibir mensagem de aviso, não quebrar."""
        with patch("conversor_moedas.msg_aviso") as mock_aviso:
            app.exibir_historico()
            mock_aviso.assert_called_once()

    @patch("builtins.print")
    def test_exibir_historico_com_dados(self, mock_print):
        """Histórico com dados deve executar sem erros."""
        app.registrar_historico(100.0, "USD", "BRL", 578.0)
        try:
            app.exibir_historico()
        except Exception as e:
            self.fail(f"exibir_historico() lançou exceção inesperada: {e}")


# ══════════════════════════════════════════════════════════
#  PONTO DE ENTRADA
# ══════════════════════════════════════════════════════════

if __name__ == "__main__":
    unittest.main(verbosity=2)

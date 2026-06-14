"""Carga inicial de dados.

Cria, na primeira execução (banco vazio):
- o login MASTER (administrador que configura todos os acessos e cadastros);
- núcleos, profissionais com perfis distintos (para testar o RBAC);
- demandas de exemplo distribuídas em status, prazos e meses, para o dashboard
  já nascer com KPIs significativos.

Se já houver um usuário master, não faz nada (idempotente).
"""
import random
from datetime import date, datetime, timedelta

import auth
import models

MASTER_EMAIL = "master@bbz.adv.br"
MASTER_SENHA = "master123"


def semear_dados(db):
    if db.query(models.Usuario).filter(models.Usuario.perfil_acesso == "master").first():
        return  # já semeado

    rnd = random.Random(42)
    hoje = date.today()

    # ---- Master + Sócio ----------------------------------------------------
    master = models.Usuario(
        nome="Administrador Master", email=MASTER_EMAIL,
        senha_hash=auth.hash_senha(MASTER_SENHA), cargo="Administrador do Sistema",
        perfil_acesso="master", carga_maxima=0,
    )
    socio = models.Usuario(
        nome="Dra. Helena Crescer", email="socio@bbz.adv.br",
        senha_hash=auth.hash_senha("socio123"), cargo="Sócia", oab="OAB/RS 12.345",
        perfil_acesso="socio", carga_maxima=40,
    )
    db.add_all([master, socio])
    db.flush()

    # ---- Núcleos -----------------------------------------------------------
    nucleos_def = [
        ("Trabalhista", "TRAB"),
        ("Cível", "CIV"),
        ("Tributário", "TRIB"),
        ("Empresarial", "EMP"),
        ("Imobiliário", "IMOB"),
    ]
    nucleos = []
    for nome, sigla in nucleos_def:
        n = models.Nucleo(nome=nome, sigla=sigla)
        db.add(n)
        nucleos.append(n)
    db.flush()

    # ---- Profissionais por núcleo -----------------------------------------
    nomes_gestores = ["Ana Lima", "Carlos Mota", "Beatriz Souza", "Diego Ramos", "Fernanda Koch"]
    nomes_adv = ["Henrique Paz", "Juliana Rios", "Marcos Pires", "Patrícia Nunes",
                 "RafaelTeixeira", "Sofia Andrade", "Tiago Mendes", "Vera Lúcia"]
    nomes_est = ["Bruno Alves", "Carla Dias", "Eduardo Reis", "Gabriela Luz"]

    profissionais = []
    for i, n in enumerate(nucleos):
        gestor = models.Usuario(
            nome=nomes_gestores[i], email=f"gestor.{n.sigla.lower()}@bbz.adv.br",
            senha_hash=auth.hash_senha("gestor123"), cargo="Gestor de Núcleo",
            oab=f"OAB/RS {20000 + i}", perfil_acesso="gestor", nucleo_id=n.id, carga_maxima=35,
        )
        db.add(gestor)
        db.flush()
        n.gestor_id = gestor.id
        profissionais.append(gestor)

    for i, nome in enumerate(nomes_adv):
        n = nucleos[i % len(nucleos)]
        adv = models.Usuario(
            nome=nome, email=f"adv{i+1}@bbz.adv.br",
            senha_hash=auth.hash_senha("adv123"), cargo="Advogado",
            oab=f"OAB/RS {30000 + i}", perfil_acesso="advogado", nucleo_id=n.id,
            gestor_id=n.gestor_id, carga_maxima=30,
        )
        db.add(adv)
        profissionais.append(adv)

    for i, nome in enumerate(nomes_est):
        n = nucleos[i % len(nucleos)]
        est = models.Usuario(
            nome=nome, email=f"estag{i+1}@bbz.adv.br",
            senha_hash=auth.hash_senha("estag123"), cargo="Estagiário",
            perfil_acesso="estagiario", nucleo_id=n.id, gestor_id=n.gestor_id, carga_maxima=15,
        )
        db.add(est)
        profissionais.append(est)
    db.flush()

    # advogados/gestores disponíveis para serem responsáveis
    responsaveis = [p for p in profissionais if p.perfil_acesso in ("advogado", "gestor")]

    tipos = ["trabalhista", "tributario", "civil", "empresarial", "imobiliario"]
    prioridades = ["urgente", "alta", "normal", "normal", "baixa"]
    titulos = [
        "Reclamatória trabalhista — horas extras", "Execução fiscal municipal",
        "Ação de cobrança", "Rescisão contratual empresarial", "Usucapião urbano",
        "Mandado de segurança tributário", "Indenização por danos morais",
        "Dissídio coletivo", "Recuperação judicial — habilitação", "Despejo por falta de pagamento",
        "Ação revisional de contrato", "Defesa em autuação fiscal", "Reintegração de posse",
        "Acordo trabalhista — homologação", "Constituição de holding familiar",
    ]

    def nova_demanda(titulo, status, criado_em, prazo_interno, valor, responsavel):
        nuc = db.get(models.Nucleo, responsavel.nucleo_id)
        d = models.Demanda(
            titulo=titulo, tipo_demanda=rnd.choice(tipos),
            status=status, prioridade=rnd.choice(prioridades),
            nucleo_id=nuc.id, criado_por=socio.id, valor_causa=valor,
            prazo_interno=prazo_interno,
            prazo_legal=prazo_interno + timedelta(days=5) if prazo_interno else None,
            numero_processo=f"{rnd.randint(1000000,9999999)}-{rnd.randint(10,99)}.2025.5.21.{rnd.randint(1000,9999)}",
            tribunal="TJRS", fase_processual=rnd.choice(["Conhecimento", "Execução", "Recursal"]),
            criado_em=criado_em, atualizado_em=criado_em,
        )
        db.add(d)
        db.flush()
        db.add(models.Movimentacao(demanda_id=d.id, profissional_id=socio.id,
                                   status_anterior=None, status_novo="triagem",
                                   observacao="Demanda criada (carga inicial)", ocorrido_em=criado_em))
        if status != "triagem":
            aloc = models.Alocacao(
                demanda_id=d.id, profissional_id=responsavel.id, papel="responsavel",
                responsavel_principal=True, horas_estimadas=rnd.randint(8, 60),
                horas_realizadas=rnd.randint(0, 40), alocado_em=criado_em,
                status="encerrado" if status in ("encerrado", "arquivado") else "ativo",
                encerrado_em=d.atualizado_em if status in ("encerrado", "arquivado") else None,
            )
            db.add(aloc)
            if status not in ("encerrado", "arquivado"):
                responsavel.carga_atual += 1
        return d

    # ---- Demandas ATIVAS (variando aging e SLA) ----------------------------
    for i in range(28):
        resp = rnd.choice(responsaveis)
        dias_atras = rnd.choice([3, 8, 12, 20, 28, 35, 50, 70])
        criado = datetime.combine(hoje - timedelta(days=dias_atras), datetime.min.time())
        # mistura de prazos: vencidos, vencendo, ok
        delta_prazo = rnd.choice([-5, -2, 1, 2, 6, 10, 20, 30])
        prazo = hoje + timedelta(days=delta_prazo)
        status = rnd.choice(["triagem", "alocacao", "execucao", "execucao", "execucao"])
        valor = rnd.choice([12000, 35000, 80000, 150000, 420000, 650000, 1200000])
        nova_demanda(rnd.choice(titulos), status, criado, prazo, valor, resp)

    # ---- Demandas ENCERRADAS nos últimos 12 meses (throughput) -------------
    ref = hoje.replace(day=1)
    for m in range(12):
        mes_ini = ref
        qtd = rnd.randint(18, 40)
        for _ in range(qtd):
            resp = rnd.choice(responsaveis)
            criado = datetime.combine(mes_ini - timedelta(days=rnd.randint(10, 40)), datetime.min.time())
            encerrado = datetime.combine(mes_ini + timedelta(days=rnd.randint(1, 26)), datetime.min.time())
            if encerrado.date() > hoje:
                encerrado = datetime.combine(hoje, datetime.min.time())
            d = nova_demanda(rnd.choice(titulos), "encerrado", criado,
                             encerrado.date(), rnd.choice([20000, 90000, 300000, 700000]), resp)
            d.atualizado_em = encerrado
            d.status = "encerrado"
        ref = (ref - timedelta(days=1)).replace(day=1)

    db.commit()
    print("=" * 64)
    print(" Banco semeado com sucesso!")
    print(f"  LOGIN MASTER:  {MASTER_EMAIL}  /  {MASTER_SENHA}")
    print("  Sócia:         socio@bbz.adv.br        / socio123")
    print("  Gestor:        gestor.trab@bbz.adv.br  / gestor123")
    print("  Advogado:      adv1@bbz.adv.br         / adv123")
    print("  Estagiário:    estag1@bbz.adv.br       / estag123")
    print("=" * 64)

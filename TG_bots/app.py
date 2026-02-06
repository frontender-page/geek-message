import flet as ft
import sqlite3
from datetime import datetime, timedelta

def main(page: ft.Page):
    # --- КОНСТАНТЫ (Цвета и Стили) ---
    BG_DARK, BG_CARD, ACCENT = "#313338", "#2b2d31", "#5865f2"
    TEXT_MUTED, BG_SIDEBAR, INPUT_BG = "#b5bac1", "#1e1f22", "#383a40"
    GOLD, RED, GREEN, PINK, ORANGE = "#FFD700", "#ff4444", "#44ff44", "#ff69b4", "#ff8800"
    SILVER, BRONZE = "#C0C0C0", "#CD7F32"

    page.title = "GeekSide | Ultimate Edition 2026"
    page.theme_mode = ft.ThemeMode.DARK
    page.bgcolor = BG_DARK
    page.window_width = 1000
    page.window_height = 800
    page.padding = 0

    input_style = {
        "bgcolor": INPUT_BG, "border_color": "transparent", "focused_border_color": ACCENT,
        "label_style": ft.TextStyle(color=TEXT_MUTED), "color": ft.Colors.WHITE,
        "text_size": 14, "height": 45, "border_radius": 10,
    }

    # --- РАБОТА С БАЗОЙ ДАННЫХ ---
    def db_query(sql, params=(), fetch=False, commit=False):
        db = sqlite3.connect('bd.geekside')
        cur = db.cursor()
        try:
            cur.execute(sql, params)
            res = cur.fetchall() if fetch else None
            if commit: db.commit()
            return res
        finally: db.close()

    # Инициализация таблиц
    db_query("CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, login TEXT, pass TEXT, about TEXT, role TEXT, mute_until TEXT)", commit=True)
    db_query("CREATE TABLE IF NOT EXISTS messages (id INTEGER PRIMARY KEY, chat_id INTEGER, user TEXT, role TEXT, text TEXT, time TEXT)", commit=True)
    db_query("CREATE TABLE IF NOT EXISTS chats (id INTEGER PRIMARY KEY, name TEXT, creator TEXT, type TEXT)", commit=True)
    db_query("CREATE TABLE IF NOT EXISTS chat_members (chat_id INTEGER, user_login TEXT)", commit=True)
    db_query("CREATE TABLE IF NOT EXISTS likes (msg_id INTEGER, user_login TEXT)", commit=True)

    if not db_query("SELECT id FROM chats WHERE id=1", fetch=True):
        db_query("INSERT INTO chats (id, name, creator, type) VALUES (1, 'общий-чат', 'System', 'public')", commit=True)

    page.user_data = {"current_user": "Гость", "role": "User", "about": ""}
    state = {"chat_id": 1, "chat_name": "общий-чат"}

    # --- ВСПОМОГАТЕЛЬНАЯ ЛОГИКА ---
    def get_user_stats(login):
        msg_count = db_query("SELECT COUNT(*) FROM messages WHERE user=?", (login,), fetch=True)[0][0]
        likes_on_my_msgs = db_query("SELECT COUNT(*) FROM likes WHERE msg_id IN (SELECT id FROM messages WHERE user=?)", (login,), fetch=True)[0][0]
        total_xp = (msg_count * 5) + (likes_on_my_msgs * 10)
        if login == "Кирилл Зубик": total_xp += 1000
        title, color, border = "Новичок", ft.Colors.WHITE, "transparent"
        if total_xp >= 1000: title, color, border = "Майор", ORANGE, ORANGE
        elif total_xp >= 500: title, color, border = "Ветеран", GREEN, GREEN
        return {"xp": total_xp, "title": title, "nick_color": color, "border_color": border}

    def get_top_rankings():
        users = db_query("SELECT login FROM users", fetch=True)
        ranks = [{"login": u[0], "xp": get_user_stats(u[0])["xp"]} for u in users]
        ranks.sort(key=lambda x: x["xp"], reverse=True)
        return ranks

    def give_xp_logic(target_login):
        for _ in range(10):
            db_query("INSERT INTO messages (chat_id, user, role, text, time) VALUES (0, ?, 'System', 'Bonus XP', '00:00')", (target_login,), commit=True)
        page.pubsub.send_all({"type": "update_ui"})
        page.snack_bar = ft.SnackBar(ft.Text(f"Выдано +50 XP для {target_login}", color=ft.Colors.WHITE), bgcolor=ORANGE)
        page.snack_bar.open = True; page.update()

    # --- УПРАВЛЕНИЕ СООБЩЕНИЯМИ (EDIT/DELETE) ---
    def open_msg_menu(msg_id, current_text, author_login):
        is_owner = author_login == page.user_data["current_user"]
        is_admin = page.user_data["role"] in ["Админ", "Создатель"]
        edit_tf = ft.TextField(value=current_text, **input_style, label="Текст сообщения")
        
        def delete_msg(_):
            db_query("DELETE FROM messages WHERE id=?", (msg_id,), commit=True)
            db_query("DELETE FROM likes WHERE msg_id=?", (msg_id,), commit=True)
            dlg.open = False; page.pubsub.send_all({"chat_id": state["chat_id"], "type": "msg"})

        def save_edit(_):
            if edit_tf.value.strip():
                db_query("UPDATE messages SET text=? WHERE id=?", (edit_tf.value, msg_id), commit=True)
                dlg.open = False; page.pubsub.send_all({"chat_id": state["chat_id"], "type": "msg"})

        btns = []
        if is_owner: btns.append(ft.ElevatedButton("Сохранить", bgcolor=ACCENT, on_click=save_edit))
        if is_owner or is_admin: btns.append(ft.TextButton("Удалить", icon=ft.Icons.DELETE, icon_color=RED, on_click=delete_msg))

        dlg = ft.AlertDialog(bgcolor=BG_CARD, title=ft.Text("Действие"), content=edit_tf if is_owner else ft.Text("Удалить чужое сообщение?"), actions=btns)
        page.overlay.append(dlg); dlg.open = True; page.update()

    # --- ИНТЕРФЕЙС ЧАТА ---
    chat_messages = ft.Column(scroll=ft.ScrollMode.ALWAYS, expand=True, spacing=10, auto_scroll=True)

    def load_messages(chat_id):
        chat_messages.controls.clear()
        msgs = db_query("SELECT id, user, role, text, time FROM messages WHERE chat_id = ?", (chat_id,), fetch=True)
        for m in msgs:
            mid, u_m, r_m, t_m, tm_m = m[0], m[1], m[2], m[3], m[4]
            if t_m == "Bonus XP": continue
            st = get_user_stats(u_m)
            is_me = u_m == page.user_data["current_user"]
            can_manage = is_me or page.user_data["role"] in ["Админ", "Создатель"]
            u_liked = db_query("SELECT 1 FROM likes WHERE msg_id=? AND user_login=?", (mid, page.user_data["current_user"]), fetch=True)
            l_cnt = db_query("SELECT COUNT(*) FROM likes WHERE msg_id=?", (mid,), fetch=True)[0][0]
            n_clr = GOLD if r_m == "Создатель" else (ACCENT if r_m == "Админ" else st["nick_color"])
            
            chat_messages.controls.append(ft.Row([
                ft.Container(
                    on_click=lambda _, i=mid, t=t_m, a=u_m: open_msg_menu(i, t, a) if can_manage else None,
                    content=ft.Column([
                        ft.Row([ft.Text(u_m, size=11, weight="bold", color=n_clr), ft.Text(tm_m, size=9, color=TEXT_MUTED)], alignment="spaceBetween", width=380),
                        ft.Text(t_m, size=14, color=ft.Colors.WHITE),
                        ft.Container(
                            on_click=lambda _, i=mid: (db_query("DELETE FROM likes WHERE msg_id=? AND user_login=?", (i, page.user_data["current_user"]), commit=True) if db_query("SELECT 1 FROM likes WHERE msg_id=? AND user_login=?", (i, page.user_data["current_user"]), fetch=True) else db_query("INSERT INTO likes (msg_id, user_login) VALUES (?, ?)", (i, page.user_data["current_user"]), commit=True), page.pubsub.send_all({"chat_id": state["chat_id"], "type": "msg"})),
                            content=ft.Row([ft.Icon(ft.Icons.FAVORITE if u_liked else ft.Icons.FAVORITE_BORDER, color=PINK if u_liked else TEXT_MUTED, size=14), ft.Text(str(l_cnt) if l_cnt > 0 else "", size=12, color=TEXT_MUTED)], spacing=4)
                        )
                    ], spacing=4),
                    bgcolor="#404249" if not is_me else ACCENT, padding=12, border_radius=15, width=400,
                    border=ft.border.all(2, st["border_color"]) if st["border_color"] != "transparent" else None
                )
            ], alignment=ft.MainAxisAlignment.END if is_me else ft.MainAxisAlignment.START))
        page.update()

    def send_msg_logic(mi):
        if page.user_data["role"] != "Создатель":
            m_r = db_query("SELECT mute_until FROM users WHERE login=?", (page.user_data["current_user"],), fetch=True)
            if m_r and m_r[0][0] and datetime.now() < datetime.fromisoformat(m_r[0][0]):
                page.snack_bar = ft.SnackBar(ft.Text("Вы в муте!")); page.snack_bar.open = True; page.update(); return
        if mi.value.strip():
            db_query("INSERT INTO messages (chat_id, user, role, text, time) VALUES (?, ?, ?, ?, ?)", (state["chat_id"], page.user_data["current_user"], page.user_data["role"], mi.value, datetime.now().strftime("%H:%M")), commit=True)
            page.pubsub.send_all({"chat_id": state["chat_id"], "type": "msg"})
            mi.value = ""; page.update()

    # --- ДИАЛОГ НОВОГО ЧАТА ---
    def open_add_chat_dialog(e):
        name_tf = ft.TextField(label="Название чата", **input_style)
        users = db_query("SELECT login FROM users WHERE login != ?", (page.user_data["current_user"],), fetch=True)
        checkboxes = {}
        user_list = ft.Column(scroll=ft.ScrollMode.AUTO, height=200)
        for u in users:
            cb = ft.Checkbox(label=u[0]); checkboxes[u[0]] = cb; user_list.controls.append(cb)

        def create_chat_logic(e):
            if not name_tf.value: return
            db_query("INSERT INTO chats (name, creator, type) VALUES (?, ?, 'private')", (name_tf.value, page.user_data["current_user"]), commit=True)
            new_id = db_query("SELECT id FROM chats ORDER BY id DESC LIMIT 1", fetch=True)[0][0]
            db_query("INSERT INTO chat_members (chat_id, user_login) VALUES (?, ?)", (new_id, page.user_data["current_user"]), commit=True)
            for login, cb in checkboxes.items():
                if cb.value: db_query("INSERT INTO chat_members (chat_id, user_login) VALUES (?, ?)", (new_id, login), commit=True)
            dlg.open = False; page.pubsub.send_all({"type": "update_ui"})

        dlg = ft.AlertDialog(bgcolor=BG_CARD, title=ft.Text("Новый чат"), content=ft.Column([name_tf, ft.Text("Пригласить:"), user_list], tight=True), actions=[ft.TextButton("Создать", on_click=create_chat_logic)])
        page.overlay.append(dlg); dlg.open = True; page.update()

    # --- НАВИГАЦИЯ ---
    def navigate(e):
        if page.user_data["current_user"] != "Гость":
            curr = db_query("SELECT role, about FROM users WHERE login=?", (page.user_data["current_user"],), fetch=True)
            if curr: page.user_data["role"], page.user_data["about"] = curr[0][0], curr[0][1]

        page.clean()
        idx = page.navigation_bar.selected_index
        
        if page.user_data["current_user"] == "Гость":
            l_in, p_in, a_in = ft.TextField(label="Логин", **input_style), ft.TextField(label="Пароль", password=True, **input_style), ft.TextField(label="О себе", **input_style)
            auth_btn = ft.ElevatedButton("Регистрация" if idx==0 else "Войти", width=350, bgcolor=ACCENT, color=ft.Colors.WHITE, on_click=lambda _: register_run(l_in, p_in, a_in) if idx==0 else auth_run(l_in, p_in))
            page.add(ft.Container(expand=True, alignment=ft.Alignment(0,0), content=ft.Column([ft.Container(width=350, padding=30, bgcolor=BG_CARD, border_radius=20, content=ft.Column([ft.Text("GeekSide", size=32, weight="bold", color=ACCENT), l_in, p_in, a_in if idx==0 else ft.Container(), auth_btn], spacing=15, horizontal_alignment="center"))], alignment="center", horizontal_alignment="center")))
        
        elif idx == 0: # ЧАТЫ
            def delete_chat_handler(chat_id_to_del):
                db_query("DELETE FROM chat_members WHERE chat_id=? AND user_login=?", (chat_id_to_del, page.user_data["current_user"]), commit=True)
                if state["chat_id"] == chat_id_to_del:
                    state["chat_id"], state["chat_name"] = 1, "общий-чат"
                page.pubsub.send_all({"type": "update_ui"})

            rows = db_query("SELECT id, name FROM chats WHERE id=1 OR id IN (SELECT chat_id FROM chat_members WHERE user_login=?)", (page.user_data["current_user"],), fetch=True)
            chat_btns = ft.Column([ft.Container(content=ft.Row([ft.Text(f"# {r[1]}", expand=True), ft.IconButton(ft.Icons.DELETE_OUTLINE, icon_color=RED, icon_size=16, on_click=lambda _, i=r[0]: delete_chat_handler(i)) if r[0] != 1 else ft.Container()], tight=True), padding=10, on_click=lambda _, i=r[0], n=r[1]: (state.update({"chat_id": i, "chat_name": n}), navigate(None)), bgcolor=ACCENT if state["chat_id"] == r[0] else "transparent", border_radius=8) for r in rows])
            
            page.add(ft.Row([
                ft.Container(width=240, bgcolor=BG_SIDEBAR, padding=15, content=ft.Column([ft.Row([ft.Text("ЧАТЫ", weight="bold"), ft.IconButton(ft.Icons.ADD_CIRCLE, icon_color=ACCENT, on_click=open_add_chat_dialog)], alignment="spaceBetween"), chat_btns])),
                ft.Container(expand=True, bgcolor=BG_DARK, padding=20, content=ft.Column([ft.Text(f"# {state['chat_name']}", size=20, weight="bold"), ft.Divider(color=BG_CARD), chat_messages, ft.Row([mi := ft.TextField(hint_text="Сообщение...", **input_style, expand=True, on_submit=lambda _: send_msg_logic(mi)), ft.IconButton(ft.Icons.SEND_ROUNDED, icon_color=ACCENT, on_click=lambda _: send_msg_logic(mi))])]))
            ], expand=True))
            load_messages(state["chat_id"])

        elif idx == 1: # РЕЙТИНГ
            ranks = get_top_rankings()
            rank_list = ft.Column(scroll="auto", expand=True, spacing=10)
            for i, r in enumerate(ranks):
                medal_color = GOLD if i == 0 else (SILVER if i == 1 else (BRONZE if i == 2 else "transparent"))
                rank_list.controls.append(ft.Container(padding=15, bgcolor=BG_CARD, border_radius=12, content=ft.Row([ft.Text(f"#{i+1}", size=18, weight="bold", color=medal_color if i < 3 else TEXT_MUTED, width=40), ft.CircleAvatar(content=ft.Text(r["login"][0]), bgcolor=ACCENT), ft.Text(r["login"], weight="bold", expand=True), ft.Column([ft.Text(f"{r['xp']} XP", color=ACCENT, weight="bold"), ft.ProgressBar(value=min(r['xp']/1000, 1.0), width=100, color=ACCENT)], horizontal_alignment="end")])))
            page.add(ft.Container(padding=30, expand=True, content=ft.Column([ft.Text("ГЛОБАЛЬНЫЙ РЕЙТИНГ", size=24, weight="bold"), ft.Divider(), rank_list])))

        else: # ПРОФИЛЬ
            stats = get_user_stats(page.user_data["current_user"])
            u_list = ft.Column(scroll="auto", height=250, spacing=10)
            for u in db_query("SELECT login, role, about, mute_until FROM users", fetch=True):
                u_l, u_r, u_a, u_m = u[0], u[1], u[2], u[3]
                u_st, act = get_user_stats(u_l), []
                if page.user_data["current_user"] == "Кирилл Зубик" and u_l != "Кирилл Зубик":
                    act.append(ft.IconButton(ft.Icons.ADD_MODERATOR, icon_color=ORANGE, on_click=lambda _, ln=u_l: give_xp_logic(ln)))
                if page.user_data["role"] in ["Создатель", "Админ"] and u_l != page.user_data["current_user"]:
                    is_m = u_m and datetime.now() < datetime.fromisoformat(u_m)
                    if page.user_data["role"] == "Создатель":
                        act.append(ft.IconButton(ft.Icons.SHIELD, icon_color=ACCENT if u_r=="Админ" else TEXT_MUTED, on_click=lambda _, ln=u_l, rl=u_r: (db_query("UPDATE users SET role=? WHERE login=?", ("User" if rl=="Админ" else "Админ", ln), commit=True), page.pubsub.send_all({"type": "update_ui"}))))
                    if u_r != "Создатель":
                        act.append(ft.IconButton(ft.Icons.BLOCK, icon_color=RED if is_m else TEXT_MUTED, on_click=lambda _, ln=u_l, m=is_m: (db_query("UPDATE users SET mute_until=? WHERE login=?", (None if m else (datetime.now()+timedelta(minutes=5)).isoformat(), ln), commit=True), page.pubsub.send_all({"type": "update_ui"}))))
                u_list.controls.append(ft.Container(padding=12, bgcolor=INPUT_BG, border_radius=12, content=ft.Row([ft.CircleAvatar(content=ft.Text(u_l[0])), ft.Column([ft.Row([ft.Text(u_l, weight="bold", color=u_st['nick_color']), ft.Text(f"• {u_st['title']} • {u_r}", size=10, color=TEXT_MUTED)]), ft.Text(u_a if u_a else "Нет описания", size=11, color=TEXT_MUTED)], expand=True), ft.Row(act)])))

            profile_card = ft.Container(width=750, bgcolor=BG_CARD, border_radius=20, content=ft.Column([
                ft.Container(height=100, bgcolor=ACCENT, border_radius=ft.border_radius.only(top_left=20, top_right=20)),
                ft.Container(padding=ft.padding.only(left=30, right=30, bottom=30, top=50), content=ft.Column([
                    ft.Row([ft.Column([ft.Text(page.user_data["current_user"], size=28, weight="bold", color=stats["nick_color"]), ft.Text(f"{stats['title']} • {page.user_data['role']}", color=ACCENT, weight="bold")]), ft.Column([ft.Text(f"{stats['xp']} XP", size=12, weight="bold"), ft.ProgressBar(value=min(stats['xp']/1000, 1.0), width=150, color=ACCENT)], horizontal_alignment="end")], alignment="spaceBetween"),
                    ft.TextField(label="О себе", value=page.user_data["about"], **input_style, on_submit=lambda e: (db_query("UPDATE users SET about=? WHERE login=?", (e.control.value, page.user_data["current_user"]), commit=True), page.update())),
                    ft.Divider(), ft.Text("УЧАСТНИКИ", weight="bold", size=12, color=TEXT_MUTED), u_list, ft.ElevatedButton("Выход", icon=ft.Icons.LOGOUT, bgcolor=RED, on_click=lambda _: logout(None))
                ]))
            ]))
            avatar = ft.Container(ft.CircleAvatar(radius=40, bgcolor=ACCENT, content=ft.Icon(ft.Icons.PERSON, size=40, color=ft.Colors.WHITE)), top=60, left=30, border=ft.border.all(4, BG_CARD), border_radius=50)
            page.add(ft.Container(expand=True, alignment=ft.Alignment(0,0), content=ft.Stack([profile_card, avatar])))
        page.update()

    # --- АУТЕНТИФИКАЦИЯ ---
    def auth_run(l, p):
        if l.value == "Кирилл Зубик" and p.value == "310713":
            if not db_query("SELECT 1 FROM users WHERE login='Кирилл Зубик'", fetch=True):
                db_query("INSERT INTO users (login, pass, role, about) VALUES ('Кирилл Зубик', '310713', 'Создатель', 'The Boss')", commit=True)
            page.user_data.update({"current_user": "Кирилл Зубик", "role": "Создатель"})
        else:
            r = db_query("SELECT login, about, role FROM users WHERE login=? AND pass=?", (l.value, p.value), fetch=True)
            if r: page.user_data.update({"current_user": r[0][0], "about": r[0][1], "role": r[0][2]})
            else: return
        page.navigation_bar.destinations = [ft.NavigationBarDestination(ft.Icons.CHAT, label="Чат"), ft.NavigationBarDestination(ft.Icons.LEADERBOARD, label="Рейтинг"), ft.NavigationBarDestination(ft.Icons.PERSON, label="Профиль")]
        page.navigation_bar.selected_index = 0; navigate(None)

    def register_run(l, p, a):
        if l.value and p.value:
            db_query("INSERT INTO users (login, pass, about, role) VALUES (?, ?, ?, ?)", (l.value, p.value, a.value, "User"), commit=True)
            page.navigation_bar.selected_index = 1; navigate(None)

    def logout(_):
        page.user_data = {"current_user": "Гость", "role": "User", "about": ""}
        page.navigation_bar.destinations = [ft.NavigationBarDestination(ft.Icons.PERSON_ADD, label="Регистрация"), ft.NavigationBarDestination(ft.Icons.LOGIN, label="Вход")]
        navigate(None)

    # --- СТАРТ ---
    page.pubsub.subscribe(lambda m: load_messages(state["chat_id"]) if m.get("chat_id")==state["chat_id"] else navigate(None))
    page.navigation_bar = ft.NavigationBar(bgcolor=BG_SIDEBAR, on_change=navigate, destinations=[ft.NavigationBarDestination(ft.Icons.PERSON_ADD, label="Регистрация"), ft.NavigationBarDestination(ft.Icons.LOGIN, label="Вход")])
    navigate(None)

ft.app(target=main, view=ft.AppView.WEB_BROWSER)
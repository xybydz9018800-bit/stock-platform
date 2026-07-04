"""
操盘平台 - 模拟交易引擎
每日从买入池选2只（1early+1mid）模拟买入，严格止损止盈
"""
from datetime import date, datetime
from engine.data_fetcher import tencent_quote
from database.models import get_connection

class SimTradeEngine:
    """模拟交易引擎"""

    def __init__(self, db_manager):
        self.db = db_manager

    def daily_pick_and_buy(self) -> dict:
        """每日模拟选股+买入"""
        pool = self.db.get_buy_pool()
        today = date.today().isoformat()

        # 分类
        early_list = [s for s in pool if s.get('phase') == 'early']
        mid_list = [s for s in pool if s.get('phase') == 'mid']

        # 按评分排序取最优
        early_list.sort(key=lambda x: x.get('total_score', 0), reverse=True)
        mid_list.sort(key=lambda x: x.get('total_score', 0), reverse=True)

        picks = []
        if early_list:
            picks.append(('early', early_list[0]))
        if mid_list:
            picks.append(('mid', mid_list[0]))

        results = []
        for phase, stock in picks:
            code = stock['code']
            name = stock.get('name', '')
            quotes = tencent_quote([code])
            q = quotes.get(code, {})

            # 以当前价作为模拟买入价（盘前就是开盘价）
            buy_price = q.get('price', 0) or stock.get('entry_price', 0)
            if buy_price <= 0:
                continue

            shares = 1000
            amount = buy_price * shares

            trade_id = self._insert_trade(today, code, name, phase, buy_price, shares, amount, stock)
            results.append({
                'trade_id': trade_id,
                'code': code,
                'name': name,
                'phase': phase,
                'buy_price': buy_price,
                'shares': shares,
                'amount': amount,
                'score': stock.get('total_score', 0),
            })

        return {
            'date': today,
            'picks': results,
            'count': len(results),
        }

    def _insert_trade(self, trade_date, code, name, phase, buy_price, shares, amount, stock):
        """插入模拟交易记录"""
        conn = get_connection()
        try:
            now_time = datetime.now().strftime('%H:%M')
            conn.execute("""
                INSERT INTO sim_trades 
                (trade_date, code, name, pool_phase, buy_price, buy_time, shares, amount, status, score_at_buy)
                VALUES (?,?,?,?,?,?,?,?,?,?)
            """, (trade_date, code, name, phase, buy_price, now_time, shares, amount, 'holding',
                 stock.get('total_score', 0)))
            conn.commit()
            return conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        finally:
            conn.close()

    def check_holding_trades(self) -> dict:
        """检查所有持仓的止盈止损信号"""
        conn = get_connection()
        try:
            holdings = conn.execute(
                "SELECT * FROM sim_trades WHERE status='holding'"
            ).fetchall()

            sold = []
            for h in holdings:
                hd = dict(h)
                code = hd['code']
                buy_price = hd['buy_price']
                quotes = tencent_quote([code])
                q = quotes.get(code, {})
                current_price = q.get('price', 0)
                if not current_price:
                    continue

                profit_pct = round((current_price / buy_price - 1) * 100, 2)
                high_p = q.get('high', current_price) or current_price
                max_gain = round((high_p / buy_price - 1) * 100, 2)
                max_loss = round((q.get('low', current_price) / buy_price - 1) * 100, 2)

                # 更新浮盈数据
                conn.execute("""
                    UPDATE sim_trades SET max_gain_pct=?, max_loss_pct=?, updated_at=datetime('now','localtime')
                    WHERE id=?
                """, (max(max_gain, hd.get('max_gain_pct', 0) or 0),
                    min(max_loss, hd.get('max_loss_pct', 0) or 0), hd['id']))

                sell_reason = None
                # 止损-5%
                if profit_pct <= -5:
                    sell_reason = 'stop_loss'
                # 移动止损：盈利>6%后回撤5%
                elif max_gain >= 6 and profit_pct <= max_gain - 5:
                    sell_reason = 'trailing_stop'
                # 持仓超过20天强制平仓
                try:
                    entry_dt = datetime.strptime(hd['trade_date'], '%Y-%m-%d')
                    hold_days = (datetime.now() - entry_dt).days
                except:
                    hold_days = 0
                if hold_days >= 20:
                    sell_reason = 'expired'

                if sell_reason:
                    sell_amount = current_price * hd['shares']
                    pl = round(sell_amount - hd['amount'], 2)
                    pl_pct = round((current_price / buy_price - 1) * 100, 2)

                    conn.execute("""
                        UPDATE sim_trades SET 
                            status='sold', sell_price=?, sell_date=?, sell_time=?,
                            profit_loss=?, profit_loss_pct=?, sell_reason=?,
                            hold_days=?, score_at_sell=?,
                            updated_at=datetime('now','localtime')
                        WHERE id=?
                    """, (current_price, date.today().isoformat(), datetime.now().strftime('%H:%M'),
                         pl, pl_pct, sell_reason, hold_days,
                         hd.get('total_score', 0) if hasattr(hd, 'total_score') else 0,
                         hd['id']))

                    sold.append({
                        'code': code, 'name': hd['name'],
                        'buy_price': buy_price, 'sell_price': current_price,
                        'profit_pct': pl_pct, 'reason': sell_reason,
                        'hold_days': hold_days,
                    })

            conn.commit()
            return {'checked': len(holdings), 'sold': len(sold), 'details': sold}
        finally:
            conn.close()

    def get_sim_trades(self, days: int = 90) -> dict:
        """获取模拟交易记录和统计"""
        conn = get_connection()
        try:
            trades = conn.execute(
                "SELECT * FROM sim_trades ORDER BY trade_date DESC, id DESC LIMIT ?",
                (days * 2,)
            ).fetchall()
            trade_list = [dict(t) for t in trades]

            # 统计
            sold_trades = [t for t in trade_list if t.get('status') == 'sold']
            wins = sum(1 for t in sold_trades if (t.get('profit_loss', 0) or 0) > 0)
            total_pnl = sum(t.get('profit_loss', 0) or 0 for t in sold_trades)
            total_pl_pct = sum(t.get('profit_loss_pct', 0) or 0 for t in sold_trades)
            avg_days = sum(t.get('hold_days', 0) or 0 for t in sold_trades) / len(sold_trades) if sold_trades else 0

            # 卖出原因分布
            reasons = {}
            for t in sold_trades:
                r = t.get('sell_reason', 'unknown')
                reasons[r] = reasons.get(r, 0) + 1

            return {
                'trades': trade_list,
                'holding': [t for t in trade_list if t.get('status') == 'holding'],
                'sold': sold_trades,
                'stats': {
                    'total_trades': len(trade_list),
                    'sold_count': len(sold_trades),
                    'holding_count': len(trade_list) - len(sold_trades),
                    'wins': wins,
                    'losses': len(sold_trades) - wins,
                    'win_rate': round(wins / len(sold_trades) * 100, 1) if sold_trades else 0,
                    'total_pnl': round(total_pnl, 2),
                    'total_pnl_pct': round(total_pl_pct, 1),
                    'avg_hold_days': round(avg_days, 1),
                    'avg_pl_pct': round(total_pl_pct / len(sold_trades), 1) if sold_trades else 0,
                    'sell_reasons': reasons,
                },
            }
        finally:
            conn.close()

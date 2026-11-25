"""No-vig multi-book consensus calculation migrated from reference; offline/pure."""
from __future__ import annotations
BOOK_WEIGHTS={"Pinnacle":3.0}
EXCLUDED_BOOKMAKERS={"Dafabet"}
MIN_BOOKMAKERS=3
def no_vig_probabilities(market):
    odds={s.get("selection"):s.get("odds",s.get("cote")) for s in market.get("selections",[]) if s.get("selection") and isinstance(s.get("odds",s.get("cote"))),(int,float)) and s.get("odds",s.get("cote"))>1.0}
    if len(odds)<2:return None
    total=sum(1/odd for odd in odds.values())
    return {sel:(1/odd)/total for sel,odd in odds.items()}
def consensus(book_markets,reference_book="1xBet",min_books=MIN_BOOKMAKERS):
    grouped={}
    for bookmaker,markets in (book_markets or {}).items():
        if bookmaker in EXCLUDED_BOOKMAKERS:continue
        for market in markets or []:
            probs=no_vig_probabilities(market)
            if not probs:continue
            key=(market.get("market",market.get("marche")),market.get("handicap"))
            grouped.setdefault(key,{})[bookmaker]=probs
    output={}
    for key,by_book in grouped.items():
        if len(by_book)<min_books:continue
        selections=set.intersection(*(set(p) for p in by_book.values())
        for sel in selections:
            weighted=[];weights=[]
            for book,probs in by_book.items():
                w=BOOK_WEIGHTS.get(book,1.0);weighted.append(probs[sel]*w);weights.append(w)
            avg=sum(weighted)/sum(weights);ref=by_book.get(reference_book,{}).get(sel)
            output[(key[0],key[1],sel)]={"probability":avg,"bookmakers":len(by_book),"reference_probability":ref,"difference_points":None if ref is None else round((avg-ref)*100,2)}
    return output

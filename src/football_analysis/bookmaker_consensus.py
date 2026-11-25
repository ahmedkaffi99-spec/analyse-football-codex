"""No-vig multi-book consensus calculation migrated from reference; offline/pure."""
BOOK_WEIGHTS={"Pinnacle":3.0}
EXCLUDED_BOOKMAKERS={"Dafabet"}
MIN_BOOKMAKERS=3
def no_vig_probabilities(market):
    odds={}
    for item in market.get("selections",[]):
        sel=item.get("selection")
        odd=item.get("odds",item.get("cote"))
        if sel and isinstance(odd,(int,float)) and odd>1.0: odds[sel]=odd
    if len(odds)<2:return None
    total=sum(1/odd for odd in odds.values())
    return {sel:(1/odd)/total for sel,odd in odds.items()}
def consensus(book_markets,reference_book="1xBet",min_books=MIN_BOOKMAKERS):
    grouped={}
    for bookmaker,markets in (book_markets or {}).items():
        if bookmaker in EXCLUDED_BOOKMAKERS:continue
        for market in markets or []:
            probs=no_vig_probabilities(market)
            if probs:
                key=(market.get("market",market.get("marche")),market.get("handicap"))
                grouped.setdefault(key,{})[bookmaker]=probs
    output={}
    for key,by_book in grouped.items():
        if len(by_book)<min_books:continue
        common=set.intersection(*(set(p) for p in by_book.values()))
        for sel in common:
            weights=[BOOK_WEIGHTS.get(book,1.0) for book in by_book]
            weighted=[by_book[book][sel]*BOOK_WEIGHTS.get(book,1.0) for book in by_book]
            avg=sum(weighted)/sum(weights)
            ref=by_book.get(reference_book,{}).get(sel)
            output[(key[0],key[1],sel)]={"probability":avg,"bookmakers":len(by_book),
                "reference_probability":ref,"difference_points":None if ref is None else round((avg-ref)*100,2)}
    return output

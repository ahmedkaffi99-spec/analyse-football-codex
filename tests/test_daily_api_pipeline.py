import unittest
from datetime import datetime,timedelta,timezone
from football_analysis.daily_api_pipeline import build_live_report,render_message

def fixture(fid,home="Home FC",away="Away FC"):
 return {"fixture":{"id":fid,"date":(datetime.now(timezone.utc)+timedelta(hours=5)).isoformat(),"status":{"short":"NS"}},"teams":{"home":{"name":home},"away":{"name":away}},"league":{"name":"Test League"}}
def odds(fid,bookmaker="1xBet"):
 return {"fixture":{"id":fid},"bookmakers":[{"id":8,"name":bookmaker,"bets":[{"id":1,"name":"Match Winner","values":[{"value":"Home","odd":"1.80"},{"value":"Draw","odd":"3.50"},{"value":"Away","odd":"4.50"}]}]}]}
class DailyApiPipelineTests(unittest.TestCase):
 def test_selects_only_upcoming_with_complete_1xbet_1x2(self):
  report=build_live_report({"response":[fixture(1),fixture(2)]},{"response":[odds(1),odds(2,"Other book")]})
  self.assertEqual(len(report["coupon"]),1); self.assertEqual(report["coupon"][0]["match_id"],"1"); self.assertEqual(report["coupon"][0]["pick"],"1"); self.assertEqual(report["bookmaker"],"1xBet")
 def test_excludes_started_fixture(self):
  row=fixture(1); row["fixture"]["date"]=(datetime.now(timezone.utc)-timedelta(hours=1)).isoformat()
  self.assertEqual(build_live_report({"response":[row]},{"response":[odds(1)]})["coupon"],[])
 def test_no_complete_market_means_no_selection(self):
  row=odds(1); row["bookmakers"][0]["bets"][0]["values"]=[{"value":"Home","odd":"1.8"}]
  report=build_live_report({"response":[fixture(1)]},{"response":[row]})
  self.assertEqual(report["coupon"],[]); self.assertIn("Aucune sélection",render_message(report))
 def test_max_legs_validation(self):
  with self.assertRaises(ValueError): build_live_report({"response":[]},{"response":[]},max_legs=0)
if __name__=="__main__": unittest.main()

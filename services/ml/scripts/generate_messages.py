"""Generate the synthetic SMS set (ARCHITECTURE.md 8.7) into data/messages.jsonl. Deterministic (fixed seed).

    python scripts/generate_messages.py [--per-template 14]

Everything is fictional: the carrier is "Nimbus", banks/couriers/agencies are made up, phone numbers are 555-01xx,
and links use the reserved .example / .test domains. Each row records the template it came from; every fourth
template of each category is marked "heldout", so evaluation measures wording the classifier never saw rather than
memorized templates. Hard negatives are deliberate: real carrier notices that mention PINs and codes, real
verification codes, real delivery links.
"""

import argparse
import json
import random
import string
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data"

NAMES = ["Alex", "Jordan", "Sam", "Riley", "Casey", "Morgan", "Taylor", "Jamie", "Drew", "Avery", "Quinn", "Reese"]
RELATIVES = ["Mom", "Dad", "Grandma", "Grandpa", "Auntie"]
BANKS = ["Cedar Bank", "Lakeside Credit Union", "Harbor Federal", "Summit Savings"]
COURIERS = ["ParcelPoint", "SwiftShip", "RouteOne Delivery"]
SHOPS = ["Northwind", "Blue Fern Market", "Copperleaf"]
AGENCIES = ["MetroPass Tolls", "State Revenue Office", "City Parking Authority"]
CLINICS = ["Riverside Dental", "Oak Street Clinic", "Maple Pharmacy"]

SCAM_HOSTS = ["nimbus-verify.test", "nimbus-secure-help.example", "nmbus-account.test", "nimbuscare-support.example",
              "acct-nimbus.test", "my-nimbus-billing.example", "go.short.test", "lnk.example"]
OTHER_SCAM_HOSTS = ["parcel-redeliver.test", "toll-settle.example", "rewards-claim.test", "secure-cedar.example",
                    "pay-fines.test", "lakeside-verify.example", "tasks-earn.test", "coin-yield.example"]
REAL_HOSTS = ["nimbus.example", "my.nimbus.example", "track.parcelpoint.example", "cedarbank.example",
              "swiftship.example", "northwind.example"]


def num():
    return f"({random.choice(['214', '469', '972', '800'])}) 555-01{random.randint(0, 99):02d}"  # 555-01xx: fictional range


def code():
    return "".join(random.choices(string.digits, k=6))


def money(lo, hi):
    return f"${random.uniform(lo, hi):.2f}"


def path():
    return "".join(random.choices(string.ascii_lowercase + string.digits, k=random.randint(4, 8)))


def scam_url():
    return f"https://{random.choice(SCAM_HOSTS)}/{path()}"


def other_url():
    return f"https://{random.choice(OTHER_SCAM_HOSTS)}/{path()}"


def real_url(host=None):
    return f"https://{host or random.choice(REAL_HOSTS)}/{path()}"


def slots():
    return {
        "carrier": random.choice(["Nimbus", "NIMBUS", "Nimbus Mobile", "Nimbus Support", "Nimbus Security"]),
        "num": num(), "code": code(), "url": scam_url(), "ourl": other_url(), "rurl": real_url(),
        "nurl": real_url(random.choice(["nimbus.example", "my.nimbus.example"])),
        "name": random.choice(NAMES), "rel": random.choice(RELATIVES), "bank": random.choice(BANKS),
        "courier": random.choice(COURIERS), "shop": random.choice(SHOPS), "agency": random.choice(AGENCIES),
        "clinic": random.choice(CLINICS), "last4": f"{random.randint(0, 9999):04d}",
        "amt": money(1.5, 9.99), "big": money(120, 980), "bill": money(35, 140),
        "day": random.choice(["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "tomorrow", "today"]),
        "time": f"{random.randint(8, 18) % 12 or 12}:{random.choice(['00', '15', '30', '45'])} {random.choice(['AM', 'PM'])}",
        "hours": random.choice(["2", "12", "24", "48"]), "pkg": f"{random.choice('ABCDEFGH')}{random.randint(10**8, 10**9 - 1)}",
    }


SCAM = {
    "carrier_impersonation": [
        "{carrier}: We detected unusual activity on your account. Call our security team now at {num} to keep your line active.",
        "This is {carrier}. Your account is flagged for verification. A specialist will call you shortly, please follow their instructions.",
        "{carrier} ALERT: someone tried to access your account from a new device. If this wasn't you, call {num} immediately.",
        "Hi, this is {name} from {carrier} support. We need to confirm your account details today to avoid service interruption. Reply YES and we will call you.",
        "{carrier}: your account will be locked in {hours} hours. Verify your identity with an agent at {num}.",
        "{carrier} Fraud Dept: a SIM change was requested on your line. To stop it call {num} now. Do not ignore.",
        "Dear customer, {carrier} is upgrading accounts. An agent will contact you to complete the update, have your account PIN ready.",
        "{carrier}: we were unable to verify your identity. Please call {num} so we can secure your number.",
    ],
    "otp_theft": [
        "{carrier}: we sent a code to your phone to cancel a SIM change request. Reply with the code to stop it.",
        "Hi it's {name}, I accidentally put your number for my verification code, can you send me the 6 digits you just got?",
        "{carrier} Security: to confirm you are the account owner, reply with the verification code we just sent.",
        "Your account recovery is pending. Text back the code you received to cancel the request.",
        "{carrier}: a login attempt needs confirming. Please read the code you received to the agent who calls you.",
        "Sorry wrong number! I sent my code to you by mistake, could you forward it to me? Thanks so much",
        "{bank}: to block the suspicious transfer reply with the one-time passcode sent to this device.",
        "{carrier}: reply with your 6-digit code within 10 min or the port request to another carrier will go through.",
    ],
    "port_out_pin": [
        "{carrier}: to complete your free 5G upgrade we need your number transfer PIN. Reply with it to continue.",
        "{carrier} account migration: please generate your port-out PIN in the app and send it to us to keep your number.",
        "Hello from {carrier}, our system update needs your transfer PIN to verify your line. Reply with the PIN.",
        "{carrier}: your number is being moved to our new network. Share your account transfer PIN with the agent at {num}.",
        "Congrats! You qualify for a loyalty discount. To apply it we need your number transfer PIN, reply here.",
        "{carrier}: a request to keep your number needs your port-out PIN today. Reply with the PIN or call {num}.",
        "To finish switching your plan please create a number transfer PIN and text it to this number.",
        "{carrier} Support: confirm ownership by replying with your transfer PIN. This keeps your number safe.",
    ],
    "sim_deactivation": [
        "{carrier}: your SIM card will be deactivated in {hours} hours due to a failed verification. Verify now: {url}",
        "Your {carrier} line is suspended. Restore service at {url}",
        "{carrier}: your SIM is outdated and will stop working {day}. Install the new eSIM profile here: {url}",
        "URGENT {carrier}: your number will be disconnected. Confirm your details at {url} to keep it.",
        "{carrier}: eSIM activation pending. Scan and install your new profile at {url} before it expires.",
        "Notice: your {carrier} SIM registration is incomplete. Complete it at {url} or lose service.",
        "{carrier}: service on your line paused for security. Reactivate: {url}",
        "Your {carrier} SIM failed a network check. Update now to avoid deactivation {url}",
    ],
    "billing_phish": [
        "{carrier}: your payment of {bill} failed. Update your card at {url} to avoid suspension.",
        "{carrier} Billing: your account is overdue. Pay now to avoid a late fee: {url}",
        "We could not process your autopay. Please re-enter your payment details: {url}",
        "{carrier}: you were overcharged {bill}. Claim your refund here {url}",
        "Final notice from {carrier}: balance of {bill} due today. Pay at {url}",
        "{carrier}: your card on file expired. Avoid service interruption, update it at {url}",
        "Billing issue on your {carrier} account. Verify your payment method within 24h {url}",
        "{carrier}: duplicate payment detected, refund of {bill} pending. Confirm bank details {url}",
    ],
    "reward_prize": [
        "{carrier} Rewards: you have 4,200 points expiring {day}! Redeem for a free phone at {url}",
        "Congratulations! You were selected for a free tablet from {carrier}. Pay {amt} shipping: {url}",
        "{carrier}: thank you for being loyal! Claim your {big} gift card now {url}",
        "You won the {carrier} customer raffle! Claim before midnight: {url}",
        "Your {shop} order qualifies for a {big} cashback reward. Claim at {ourl}",
        "{carrier} loyalty bonus: free upgrade waiting for you, just confirm shipping {amt} at {url}",
        "Exclusive: you've been chosen for a survey with a {big} reward. Start now {ourl}",
        "Your {carrier} points are about to expire! Use them today at {url}",
    ],
    "delivery_fee": [
        "{courier}: your package {pkg} is held at our depot. Pay {amt} redelivery fee: {ourl}",
        "{courier}: we missed you. Reschedule delivery and pay {amt} at {ourl}",
        "Your parcel could not be delivered due to an incomplete address. Update it here {ourl}",
        "{courier} notice: customs fee of {amt} required for package {pkg}. Pay now {ourl}",
        "Package {pkg} awaiting payment of {amt} before delivery. {ourl}",
        "{courier}: final attempt for your delivery today. Confirm details and fee {ourl}",
        "Your {shop} package is on hold, a small fee of {amt} is needed: {ourl}",
        "{courier}: delivery suspended, address verification needed {ourl}",
    ],
    "toll_government": [
        "{agency}: you have an unpaid toll of {amt}. Pay by {day} to avoid a {bill} penalty: {ourl}",
        "{agency}: final notice for outstanding balance. Settle now to avoid legal action {ourl}",
        "{agency}: our records show an unpaid fine. Pay within {hours} hours: {ourl}",
        "Your tax refund of {big} is ready. Submit your bank details to receive it: {ourl}",
        "{agency}: your vehicle has an unpaid toll. Late fees apply after {day}. {ourl}",
        "Notice of overdue parking ticket. Pay online now {ourl} or your license may be suspended.",
        "{agency}: you are owed a refund. Confirm your identity to claim {ourl}",
        "Unpaid toll balance {amt} detected for your plate. Avoid fees: {ourl}",
    ],
    "bank_alert": [
        "{bank} Fraud Alert: did you attempt a {big} purchase? If not call {num} immediately.",
        "{bank}: your card ending {last4} has been locked. Call {num} to unlock it.",
        "{bank}: suspicious login detected. Verify your account at {ourl}",
        "{bank}: a transfer of {big} is pending. Reply NO to cancel or call {num}.",
        "{bank} Security: please confirm your online banking details to keep your account open {ourl}",
        "{bank}: your account is restricted. Restore access at {ourl}",
        "{bank}: we blocked a {big} charge. An agent will call you to verify your card number.",
        "{bank} ALERT: unusual activity on your debit card ending {last4}. Call {num} now.",
    ],
    "family_emergency": [
        "Hi {rel} it's me, I dropped my phone and this is my new number. Can you text me here?",
        "{rel} I'm in trouble and need {big} right away, please don't tell anyone, I'll explain later",
        "Hey {rel}, new phone! Mine broke. Can you help me pay a bill today? I'll pay you back",
        "Hi it's me, using a friend's phone. I need money for a ticket home, can you send {big}?",
        "{rel}, I had a car accident and need help with the deposit. Please send it quickly",
        "This is my new number, save it. Are you free? I need a small favor urgently",
        "Hi {rel} my bank card got blocked, can you transfer {big} to my friend's account for me?",
        "It's me {rel}, please don't call I can't talk right now, just reply here. I need help",
    ],
    "wrong_number": [
        "Hi, is this {name}? We met at the conference last week",
        "Hey {name}, are we still on for dinner {day}?",
        "Sorry, I think I got the wrong number. You seem nice though, where are you from?",
        "Hello, is this {name}'s number? My assistant gave it to me",
        "Good morning! Is this {name}? I wanted to follow up about the apartment",
        "Hi {name}, long time no see! How have you been?",
        "Oops, wrong person. Since we're chatting, do you live in the area?",
        "Hi, this is {name}'s friend. She said you could help me with investing?",
    ],
    "job_task": [
        "Hi, I'm a recruiter. We have a remote job paying {big} per day, flexible hours. Interested? Reply YES",
        "Part-time online work: rate products from home and earn {big} daily. Message us on our app {ourl}",
        "Your resume was selected for a remote position. Contact HR on chat to start today.",
        "Earn {big} a day completing simple tasks on your phone. No experience needed {ourl}",
        "Hello, we are hiring for a work-from-home assistant, {big} weekly. Reply to learn more",
        "Job offer: data entry from home, paid daily. Start now {ourl}",
        "You've been shortlisted for a high-paying online job. Add our coordinator on chat to begin",
        "Make money boosting app reviews, pay daily, training provided {ourl}",
    ],
    "investment_crypto": [
        "Join our private group and earn 30% weekly with crypto signals. Limited spots: {ourl}",
        "Guaranteed returns on our trading platform, start with just $100. {ourl}",
        "Your crypto wallet has a pending reward of {big}. Withdraw now {ourl}",
        "Our mentor turned $500 into {big} in a week. Join the group today {ourl}",
        "Investment opportunity: double your money in 14 days, no risk {ourl}",
        "Bitcoin is exploding, don't miss out. Our experts guarantee profits {ourl}",
        "Exclusive pre-sale for a new coin, guaranteed 10x. Buy before {day}: {ourl}",
        "Hi, I made a lot trading gold with this app, want me to show you? {ourl}",
    ],
}

HAM = {
    "carrier_notice": [
        "{carrier}: your bill of {bill} is ready. View it in the Nimbus app or at {nurl}. Reply STOP to opt out.",
        "{carrier}: thanks! Your autopay payment of {bill} was received.",
        "{carrier}: your plan change takes effect on your next bill. No action needed.",
        "{carrier}: reminder, Nimbus will never ask for your account PIN, transfer PIN, or a verification code by text or phone.",
        "{carrier}: you've used 80% of your hotspot data this month. Manage your plan in the Nimbus app.",
        "{carrier}: your transfer PIN was viewed in your account. If this wasn't you, sign in to the Nimbus app and change your password.",
        "{carrier}: a new device signed in to your account. If it was you, no action needed.",
        "{carrier}: your new SIM has been activated. If you didn't request this, contact us through the Nimbus app.",
        "{carrier}: your device payment of {bill} is scheduled for {day}.",
        "{carrier}: international roaming is now on for your trip. Rates are in the Nimbus app.",
        "{carrier}: we've received your trade-in. Your credit of {bill} will show on your next bill.",
        "{carrier}: your appointment at the Nimbus store is confirmed for {day} at {time}.",
        "{carrier}: network maintenance in your area tonight may briefly affect service. Thanks for your patience.",
        "{carrier}: your password was changed. If this wasn't you, sign in to the Nimbus app to secure your account.",
        "{carrier}: your eSIM is ready. Finish setup in your phone's settings using the Nimbus app.",
        "{carrier}: welcome! Your line is active. Manage your account at {nurl}",
    ],
    "verification_code": [
        "{carrier}: your verification code is {code}. Don't share it with anyone. Nimbus will never ask for it.",
        "{code} is your {shop} login code. It expires in 10 minutes.",
        "Your {bank} one-time code is {code}. We will never call you to ask for this code.",
        "Use {code} to verify your {carrier} account. If you didn't request this, ignore this message.",
        "{shop}: {code} is your security code. Do not share it.",
        "Your sign-in code is {code}. Only enter it on the official site or app.",
        "{bank}: {code} is your code to approve the payment you just made online.",
        "{carrier}: code {code}. Enter it in the app to finish signing in.",
        "{code} is your verification code for {shop}. Never share this code.",
        "Your {carrier} password reset code is {code}. If you didn't ask for it, you can ignore this.",
        "{bank}: enter {code} to confirm it's you. We'll never ask you to share it.",
        "Here is your one-time passcode: {code}. Valid for 5 minutes.",
    ],
    "delivery_update": [
        "{courier}: your package {pkg} is out for delivery today. Track it at {rurl}",
        "{shop}: your order has shipped and will arrive {day}.",
        "{courier}: package {pkg} was delivered to your front door.",
        "{courier}: your delivery is scheduled for {day} between 10 AM and 2 PM.",
        "{shop}: your order is ready for pickup at the store.",
        "{courier}: we'll deliver package {pkg} {day}. No action needed.",
        "Your {shop} return was received. Refund in 3-5 days.",
        "{courier}: delivery update for {pkg}: arriving early, today by 6 PM.",
    ],
    "bank_notice": [
        "{bank}: a purchase of {bill} was made with your card ending {last4}.",
        "{bank}: your balance is below $100. Check your account in the app.",
        "{bank}: your direct deposit of {big} has arrived.",
        "{bank}: your monthly statement is ready in online banking.",
        "{bank}: your card ending {last4} will expire next month. A new one is on the way.",
        "{bank}: you sent {bill} to {name}.",
        "{bank}: your scheduled transfer of {bill} is complete.",
        "{bank}: a new payee was added to your account. If this wasn't you, call the number on the back of your card.",
    ],
    "appointment": [
        "{clinic}: reminder of your appointment {day} at {time}. Reply C to confirm.",
        "{clinic}: your prescription is ready for pickup.",
        "Your table for 4 at Lantern House is confirmed for {day} at {time}.",
        "{clinic}: please arrive 10 minutes early for your visit {day}.",
        "Reminder: car service appointment {day} at {time}.",
        "{clinic}: your refill request was approved.",
        "Your haircut with {name} is booked for {day} at {time}.",
        "School notice: early dismissal {day} at {time}.",
    ],
    "personal": [
        "Running 10 min late, save me a seat",
        "Did you see the game last night??",
        "Can you pick up milk on the way home?",
        "Happy birthday!! Hope you have a great day",
        "Hey {name}, are we still on for {day}?",
        "Just landed, will call you in a bit",
        "lol that's amazing, send me the pic",
        "Thanks for dinner, it was great to see you",
        "Don't forget mom's thing on {day}",
        "Can you send me the address again?",
        "ok sounds good, see you at {time}",
        "Leaving now, be there in 20",
        "what time works for you tomorrow",
        "I'm outside",
        "Call me when you get a sec",
        "Great job today!",
        "Can't make it tonight, sorry. Rain check?",
        "Did you feed the dog?",
        "omw",
        "Love you, drive safe",
        "The kids want pizza for dinner, ok with you?",
        "Meeting moved to {time}",
        "Sending you the photos from the weekend now",
        "Who's bringing the snacks {day}?",
        "Just finished, heading home",
        "Can you call grandma back? She tried to reach you",
        "Thanks again for the help with the move",
        "Movie starts at {time}, want to grab food first?",
        "Got your package, thank you so much!",
        "How did the interview go?",
        "Traffic is terrible, going to be late",
        "{name} says hi",
        "Can I borrow your ladder this weekend?",
        "Remember to bring your ID {day}",
        "Good luck on your test!",
        "That's hilarious 😂",
    ],
    "marketing": [
        "{shop}: 20% off this weekend in store and online. Reply STOP to opt out.",
        "{carrier}: new phones are in! See this month's deals in the Nimbus app. Reply STOP to opt out.",
        "{shop}: your favorites are back in stock. Shop at {rurl} Reply STOP to unsubscribe.",
        "Lantern House: happy hour specials every Friday. Reply STOP to opt out.",
        "{shop} members: double points on all purchases {day}. Reply STOP to end.",
        "{carrier}: add a line for $20/mo this month. Details in the Nimbus app. STOP to opt out.",
        "{shop}: free shipping on orders over $50 this week. Reply STOP to opt out.",
        "{shop}: thanks for shopping with us! Rate your visit {rurl} STOP to quit.",
    ],
}


def noise(text: str, scam: bool) -> str:
    """Light variation so templates don't produce identical strings. Scams get a bit more shouting and emoji."""
    r = random.random()
    if scam and r < 0.12:
        text = text.upper()
    elif r < 0.2:
        text = text.replace(". ", ".  ", 1)
    if random.random() < (0.15 if scam else 0.05):
        text += random.choice([" ⚠️", " 📦", " ❗", " 🎁", " ✅"])
    if random.random() < 0.08:
        i = random.randrange(len(text))
        text = text[:i] + text[i + 1:]  # a dropped character
    return text


def build(per_template: int) -> list[dict]:
    rows = []
    for label, groups in (("scam", SCAM), ("ham", HAM)):
        for cat, templates in groups.items():
            for ti, tpl in enumerate(templates):
                split = "heldout" if ti % 4 == 3 else "train"
                n = per_template if label == "scam" else per_template + 8  # fewer ham categories: more per template
                for _ in range(n):
                    text = noise(tpl.format(**slots()), label == "scam")
                    rows.append({"text": text, "label": label, "category": cat, "template": f"{cat}:{ti}", "split": split})
    random.shuffle(rows)
    for i, r in enumerate(rows):
        r["id"] = f"m{i:05d}"
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--per-template", type=int, default=14)
    args = ap.parse_args()
    random.seed(20261108)
    rows = build(args.per_template)
    DATA.mkdir(exist_ok=True)
    with open(DATA / "messages.jsonl", "w") as f:
        for r in rows:
            f.write(json.dumps({k: r[k] for k in ("id", "text", "label", "category", "template", "split")}) + "\n")
    scam = sum(r["label"] == "scam" for r in rows)
    held = sum(r["split"] == "heldout" for r in rows)
    print(f"wrote {len(rows)} messages ({scam} scam, {len(rows) - scam} ham; {held} heldout) to {DATA / 'messages.jsonl'}")


if __name__ == "__main__":
    main()

import pandas as pd
from pathlib import Path

gold_data = [
    {
        "ticket_id": "TK-240469",
        "gold_issue_code": "DELIVERY",
        "gold_sub_issue": "marked_delivered_not_received",
        "gold_repeat_relevant": False,
        "review_notes": "Courier marked order as delivered but customer received nothing."
    },
    {
        "ticket_id": "TK-240594",
        "gold_issue_code": "RETURNS",
        "gold_sub_issue": "reverse_pickup_pending",
        "gold_repeat_relevant": False,
        "review_notes": "Customer packed return box a week ago, pickup still pending."
    },
    {
        "ticket_id": "TK-240704",
        "gold_issue_code": "RETURNS",
        "gold_sub_issue": "reverse_pickup_missed",
        "gold_repeat_relevant": True,
        "review_notes": "Nobody came for pickup after customer rescheduled twice."
    },
    {
        "ticket_id": "TK-241306",
        "gold_issue_code": "RETURNS",
        "gold_sub_issue": "refund_status",
        "gold_repeat_relevant": True,
        "review_notes": "Customer awaiting refund after return, mentions emailed twice."
    },
    {
        "ticket_id": "TK-241450",
        "gold_issue_code": "APP",
        "gold_sub_issue": "app_crash",
        "gold_repeat_relevant": True,
        "review_notes": "Nexa Fit app crashes when opening device settings; agent notes confirm prior contact."
    },
    {
        "ticket_id": "TK-241896",
        "gold_issue_code": "DELIVERY",
        "gold_sub_issue": "delayed_delivery",
        "gold_repeat_relevant": True,
        "review_notes": "Fit band delivery delayed, package not received; agent notes state cx contacted earlier."
    },
    {
        "ticket_id": "TK-241989",
        "gold_issue_code": "WARRANTY",
        "gold_sub_issue": "service_center_status",
        "gold_repeat_relevant": True,
        "review_notes": "Customer sent Strata 3 headphones in 8 days ago and follows up on warranty status."
    },
    {
        "ticket_id": "TK-242590",
        "gold_issue_code": "BILLING",
        "gold_sub_issue": "invoice_request",
        "gold_repeat_relevant": False,
        "review_notes": "Customer asks for GSTIN bill on firm name (also includes boilerplate replacement phrase)."
    },
    {
        "ticket_id": "TK-242633",
        "gold_issue_code": "OTHER",
        "gold_sub_issue": "pre_sales_compatibility",
        "gold_repeat_relevant": False,
        "review_notes": "Pre-sales query asking if earbuds will work with 2019 Samsung phone."
    },
    {
        "ticket_id": "TK-243268",
        "gold_issue_code": "DELIVERY",
        "gold_sub_issue": "delayed_delivery",
        "gold_repeat_relevant": False,
        "review_notes": "Orbit speaker ordered 2 weeks ago has not arrived."
    },
    {
        "ticket_id": "TK-243363",
        "gold_issue_code": "PRODUCT",
        "gold_sub_issue": "bluetooth_pairing",
        "gold_repeat_relevant": True,
        "review_notes": "Orbit speaker not pairing with phone, customer explicitly mentions raised 2 weeks ago."
    },
    {
        "ticket_id": "TK-243396",
        "gold_issue_code": "PRODUCT",
        "gold_sub_issue": "battery_drain",
        "gold_repeat_relevant": False,
        "review_notes": "Strata 2 headphone battery life dropped to almost nothing."
    },
    {
        "ticket_id": "TK-243403",
        "gold_issue_code": "BILLING",
        "gold_sub_issue": "payment_failed_order_not_created",
        "gold_repeat_relevant": False,
        "review_notes": "Payment completed on gateway but no order created in account."
    },
    {
        "ticket_id": "TK-243641",
        "gold_issue_code": "OTHER",
        "gold_sub_issue": "product_compatibility",
        "gold_repeat_relevant": False,
        "review_notes": "Product compatibility query asking if Pulse 2 works with TV."
    },
    {
        "ticket_id": "TK-243746",
        "gold_issue_code": "DELIVERY",
        "gold_sub_issue": "delayed_delivery",
        "gold_repeat_relevant": False,
        "review_notes": "Customer paid on 02/08 and shipment has not arrived."
    },
    {
        "ticket_id": "TK-244208",
        "gold_issue_code": "BILLING",
        "gold_sub_issue": "coupon_code_error",
        "gold_repeat_relevant": False,
        "review_notes": "Discount coupon code failing to apply during checkout."
    },
    {
        "ticket_id": "TK-244806",
        "gold_issue_code": "BILLING",
        "gold_sub_issue": "discount_not_applied",
        "gold_repeat_relevant": False,
        "review_notes": "Promotional discount not applied at checkout on Nexa 2 watch."
    },
    {
        "ticket_id": "TK-245357",
        "gold_issue_code": "PRODUCT",
        "gold_sub_issue": "bluetooth_dropouts",
        "gold_repeat_relevant": True,
        "review_notes": "Orbit Mini audio disconnects every few minutes; agent notes confirm repeat contact."
    },
    {
        "ticket_id": "TK-245395",
        "gold_issue_code": "DELIVERY",
        "gold_sub_issue": "delayed_delivery",
        "gold_repeat_relevant": True,
        "review_notes": "Customer states same complaint order not delivered; agent notes confirm repeat contact."
    },
    {
        "ticket_id": "TK-246040",
        "gold_issue_code": "RETURNS",
        "gold_sub_issue": "refund_status",
        "gold_repeat_relevant": True,
        "review_notes": "Waiting for refund for returned Pulse 2, customer emailed twice."
    },
    {
        "ticket_id": "TK-246465",
        "gold_issue_code": "PRODUCT",
        "gold_sub_issue": "audio_distortion",
        "gold_repeat_relevant": True,
        "review_notes": "Distorted audio at high volume on Pulse 2, fourth time writing."
    },
    {
        "ticket_id": "TK-247017",
        "gold_issue_code": "PRODUCT",
        "gold_sub_issue": "power_button_failure",
        "gold_repeat_relevant": False,
        "review_notes": "Power button does not respond after holding 30 seconds."
    },
    {
        "ticket_id": "TK-247836",
        "gold_issue_code": "PRODUCT",
        "gold_sub_issue": "single_side_dead",
        "gold_repeat_relevant": False,
        "review_notes": "Strata 2 headphones one side has failed and is dead."
    },
    {
        "ticket_id": "TK-248233",
        "gold_issue_code": "APP",
        "gold_sub_issue": "firmware_update_hang",
        "gold_repeat_relevant": False,
        "review_notes": "Firmware update progress bar has not moved since morning."
    },
    {
        "ticket_id": "TK-248572",
        "gold_issue_code": "OTHER",
        "gold_sub_issue": "account_login_otp",
        "gold_repeat_relevant": False,
        "review_notes": "Customer cannot log into account, OTP not received."
    },
    {
        "ticket_id": "TK-248721",
        "gold_issue_code": "RETURNS",
        "gold_sub_issue": "refund_status",
        "gold_repeat_relevant": True,
        "review_notes": "Customer still waiting for refund, emailed twice."
    },
    {
        "ticket_id": "TK-249010",
        "gold_issue_code": "DELIVERY",
        "gold_sub_issue": "delivery_address_change",
        "gold_repeat_relevant": False,
        "review_notes": "Customer entered wrong pincode and needs delivery address corrected."
    },
    {
        "ticket_id": "TK-249148",
        "gold_issue_code": "RETURNS",
        "gold_sub_issue": "reverse_pickup_missed",
        "gold_repeat_relevant": True,
        "review_notes": "Nobody came for pickup, customer rescheduled twice."
    },
    {
        "ticket_id": "TK-250128",
        "gold_issue_code": "BILLING",
        "gold_sub_issue": "invoice_request",
        "gold_repeat_relevant": False,
        "review_notes": "Customer request for invoice with GST number."
    },
    {
        "ticket_id": "TK-250205",
        "gold_issue_code": "BILLING",
        "gold_sub_issue": "invoice_request",
        "gold_repeat_relevant": False,
        "review_notes": "Request for GST invoice for Pulse 2 order."
    },
    {
        "ticket_id": "TK-250492",
        "gold_issue_code": "PRODUCT",
        "gold_sub_issue": "single_side_no_audio",
        "gold_repeat_relevant": False,
        "review_notes": "Pulse 1 left earbud has no audio output at all."
    },
    {
        "ticket_id": "TK-250548",
        "gold_issue_code": "PRODUCT",
        "gold_sub_issue": "bluetooth_pairing",
        "gold_repeat_relevant": False,
        "review_notes": "Strata 3 headphones cannot pair with laptop."
    },
    {
        "ticket_id": "TK-250741",
        "gold_issue_code": "BILLING",
        "gold_sub_issue": "payment_failed_order_not_created",
        "gold_repeat_relevant": False,
        "review_notes": "Payment deducted from account but order was not generated."
    },
    {
        "ticket_id": "TK-251128",
        "gold_issue_code": "RETURNS",
        "gold_sub_issue": "reverse_pickup_missed",
        "gold_repeat_relevant": True,
        "review_notes": "Nexa 2 return pickup has not happened, customer rescheduled twice."
    },
    {
        "ticket_id": "TK-251343",
        "gold_issue_code": "PRODUCT",
        "gold_sub_issue": "audio_distortion",
        "gold_repeat_relevant": True,
        "review_notes": "Hissing noise in AirLite earbuds, customer states this was supposedly sorted last time."
    },
    {
        "ticket_id": "TK-251734",
        "gold_issue_code": "RETURNS",
        "gold_sub_issue": "refund_status",
        "gold_repeat_relevant": False,
        "review_notes": "Return was accepted but refund amount not reflected in account."
    },
    {
        "ticket_id": "TK-251835",
        "gold_issue_code": "PRODUCT",
        "gold_sub_issue": "bluetooth_pairing",
        "gold_repeat_relevant": False,
        "review_notes": "Pulse 1 earbuds not pairing with phone."
    },
    {
        "ticket_id": "TK-251976",
        "gold_issue_code": "PRODUCT",
        "gold_sub_issue": "battery_drain",
        "gold_repeat_relevant": False,
        "review_notes": "Strata 3 headphone battery drains from full to empty during single commute."
    },
    {
        "ticket_id": "TK-251994",
        "gold_issue_code": "PRODUCT",
        "gold_sub_issue": "bluetooth_pairing",
        "gold_repeat_relevant": False,
        "review_notes": "Pulse 2 earbuds not pairing with smartphone."
    },
    {
        "ticket_id": "TK-252194",
        "gold_issue_code": "DELIVERY",
        "gold_sub_issue": "damaged_in_transit",
        "gold_repeat_relevant": False,
        "review_notes": "Package box crushed and Nexa 2 watch screen cracked in transit."
    },
    {
        "ticket_id": "TK-252349",
        "gold_issue_code": "DELIVERY",
        "gold_sub_issue": "delayed_delivery",
        "gold_repeat_relevant": False,
        "review_notes": "Order not delivered and tracking information stuck."
    },
    {
        "ticket_id": "TK-252647",
        "gold_issue_code": "DELIVERY",
        "gold_sub_issue": "delayed_delivery",
        "gold_repeat_relevant": True,
        "review_notes": "Customer says same problem again, order not received after courier follow-up."
    },
    {
        "ticket_id": "TK-252689",
        "gold_issue_code": "BILLING",
        "gold_sub_issue": "invoice_request",
        "gold_repeat_relevant": False,
        "review_notes": "Request for GST invoice for Pulse 2 order."
    },
    {
        "ticket_id": "TK-253062",
        "gold_issue_code": "APP",
        "gold_sub_issue": "app_crash",
        "gold_repeat_relevant": False,
        "review_notes": "Orbit companion app not opening after latest update."
    },
    {
        "ticket_id": "TK-253533",
        "gold_issue_code": "BILLING",
        "gold_sub_issue": "payment_failed_order_not_created",
        "gold_repeat_relevant": False,
        "review_notes": "Bank deducted Rs 4999 but site shows no order."
    },
    {
        "ticket_id": "TK-253656",
        "gold_issue_code": "DELIVERY",
        "gold_sub_issue": "delayed_delivery",
        "gold_repeat_relevant": True,
        "review_notes": "Customer writes yet again haven't received order."
    },
    {
        "ticket_id": "TK-253893",
        "gold_issue_code": "DELIVERY",
        "gold_sub_issue": "delayed_delivery",
        "gold_repeat_relevant": False,
        "review_notes": "Pulse 2 order stuck on shipped status since May 09."
    },
    {
        "ticket_id": "TK-254182",
        "gold_issue_code": "DELIVERY",
        "gold_sub_issue": "delivery_address_change",
        "gold_repeat_relevant": False,
        "review_notes": "Typo in flat number, customer requests address correction."
    },
    {
        "ticket_id": "TK-254240",
        "gold_issue_code": "DELIVERY",
        "gold_sub_issue": "delayed_delivery",
        "gold_repeat_relevant": False,
        "review_notes": "Pulse 2 earbuds ordered 10 days ago not yet delivered."
    },
    {
        "ticket_id": "TK-254841",
        "gold_issue_code": "DELIVERY",
        "gold_sub_issue": "order_cancellation",
        "gold_repeat_relevant": False,
        "review_notes": "Order cancellation requested before dispatch (cancel button greyed out)."
    }
]

df = pd.DataFrame(gold_data)
Path("evaluation").mkdir(exist_ok=True)
df.to_csv("evaluation/phase3_gold_labels.csv", index=False)
print(f"Saved evaluation/phase3_gold_labels.csv with {len(df)} rows.")

"""Seed a realistic demo dataset through the domain services (never raw inserts), so demo
data obeys the same rules, history, audit trail and notifications as real usage.

    python manage.py seed_demo

All names are fictional. Every demo account uses the password printed at the end.
"""

from datetime import timedelta
from zoneinfo import ZoneInfo

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.identity import services as identity
from apps.identity.models import User
from apps.messaging import services as messaging
from apps.opportunities import services as opp
from apps.outbox.services import process_pending
from apps.profiles import services as profiles
from apps.social import services as social

PASSWORD = "eqora-demo-2026"


class Command(BaseCommand):
    help = "Create fictional demo users, gigs, applications, posts and messages."

    def handle(self, *args, **options):
        if User.objects.filter(email="asha@demo.eqora").exists():
            self.stdout.write("Demo data already present.")
            return self._print_logins()
        with transaction.atomic():
            self._seed()
        process_pending()
        self.stdout.write(self.style.SUCCESS("Demo data created."))
        self._print_logins()

    def _print_logins(self):
        self.stdout.write(f"  artist:    asha@demo.eqora / {PASSWORD}")
        self.stdout.write(f"  organizer: olivia@demo.eqora / {PASSWORD}")

    def _user(self, email, name, roles, profile, artist=None, organizer=None):
        user = identity.register_user(email=email, password=PASSWORD, display_name=name, roles=roles)
        profiles.update_own_profile(user, core=profile, artist=artist, organizer=organizer)
        return user

    def _seed(self):
        # Wall-clock times are local to the venue: 8pm means 8pm in Bengaluru, not 8pm UTC.
        local_now = timezone.localtime(timezone.now(), ZoneInfo("Asia/Kolkata"))
        day = lambda n, h=20: (local_now + timedelta(days=n)).replace(  # noqa: E731
            hour=h, minute=0, second=0, microsecond=0
        )

        asha = self._user(
            "asha@demo.eqora", "Asha Rao", ["artist"],
            {"headline": "Indie-folk singer-songwriter", "location_label": "Bengaluru",
             "bio": "Writing songs about monsoons and metro rides. Guitar + loop pedal. "
                    "Two EPs out, always up for an open mic."},
            artist={"artist_name": "Asha Rao", "genres": ["indie", "folk", "acoustic"],
                    "skills": ["singing", "guitar"],
                    "experience_summary": "60+ live sets across Bengaluru and Pune."},
        )
        profiles.add_portfolio_item(asha, {"title": "Monsoon Letters (live session)",
                                           "url": "https://www.youtube.com/watch?v=demo1",
                                           "item_type": "video"})
        profiles.add_portfolio_item(asha, {"title": "Metro Lines EP",
                                           "url": "https://soundcloud.com/demo/metro-lines",
                                           "item_type": "audio"})
        kabir = self._user("kabir@demo.eqora", "Kabir Sethi", ["artist"],
                           {"headline": "House & disco DJ", "location_label": "Mumbai"},
                           artist={"genres": ["electronic"], "skills": ["djing", "music-production"]})
        meera = self._user("meera@demo.eqora", "Meera Iyer", ["artist"],
                           {"headline": "Jazz vocalist · standards & originals",
                            "location_label": "Bengaluru"},
                           artist={"genres": ["jazz", "soul"], "skills": ["singing"]})
        dev = self._user("dev@demo.eqora", "Dev & The Dusk", ["artist"],
                         {"headline": "Four-piece alt-rock band", "location_label": "Bengaluru"},
                         artist={"genres": ["rock", "indie"], "skills": ["guitar", "drums", "bass"]})
        olivia = self._user(
            "olivia@demo.eqora", "Olivia Fernandes", ["organizer", "artist"],
            {"headline": "Curator · The Loft Sessions", "location_label": "Bengaluru",
             "bio": "Running weekly acoustic nights since 2019. Every artist deserves a stage."},
            organizer={"organization_name": "The Loft Sessions"},
        )
        rohan = self._user("rohan@demo.eqora", "Rohan Mehta", ["organizer"],
                           {"headline": "Festival booker · Neon Nights", "location_label": "Mumbai"},
                           organizer={"organization_name": "Neon Nights"})

        venue = profiles.create_venue(olivia, {"name": "The Loft", "city": "Bengaluru",
                                               "address_text": "Indiranagar", "capacity": 120})

        # Event with several independently apply-able slots.
        loft = opp.create_event(olivia, {
            "title": "Loft Sessions: Friday Acoustic Night", "venue": venue,
            "description": "Our weekly acoustic night. Warm crowd, good sound, great chai.",
            "starts_at": day(4), "location_text": "The Loft, Indiranagar, Bengaluru",
            "timezone": "Asia/Kolkata",
        })
        opp.publish_event(olivia, loft.id)
        open_mic = opp.create_opportunity(olivia, {
            "event": loft, "title": "Acoustic open mic — 15 min sets",
            "description": "Two songs or fifteen minutes, whichever comes first. Originals encouraged. "
                           "We provide a vocal mic, DI box and a house guitar if you need one.",
            "opportunity_type": "open_mic_slot", "compensation_type": "unpaid", "capacity": 6,
            "starts_at": day(4), "application_deadline": day(3, 18),
            "location_text": "The Loft, Indiranagar", "timezone": "Asia/Kolkata",
            "requirements": "Bring a link to one live performance.",
            "genres": ["acoustic", "folk", "indie"], "skills": ["singing"],
        })
        opp.publish_opportunity(olivia, open_mic.id)
        feature = opp.create_opportunity(olivia, {
            "event": loft, "title": "Featured artist — 40 min headline set",
            "description": "Close the night with a full set. Sound check at 6pm.",
            "opportunity_type": "paid_gig", "compensation_type": "paid",
            "compensation_amount": "8000", "currency": "INR", "capacity": 1,
            "starts_at": day(4, 22), "application_deadline": day(2, 18),
            "location_text": "The Loft, Indiranagar", "timezone": "Asia/Kolkata",
            "genres": ["indie", "folk"],
        })
        opp.publish_opportunity(olivia, feature.id)
        host = opp.create_opportunity(olivia, {
            "event": loft, "title": "Host / MC for the night",
            "description": "Keep the energy up between sets and introduce each artist.",
            "opportunity_type": "host_role", "compensation_type": "paid",
            "compensation_amount": "3000", "currency": "INR", "capacity": 1,
            "starts_at": day(4), "application_deadline": day(3), "location_text": "The Loft",
            "timezone": "Asia/Kolkata",
        })
        opp.publish_opportunity(olivia, host.id)

        neon = opp.create_event(rohan, {
            "title": "Neon Nights Rooftop", "description": "Sunset-to-late rooftop party.",
            "starts_at": day(12, 18), "location_text": "Lower Parel, Mumbai",
            "timezone": "Asia/Kolkata",
        })
        opp.publish_event(rohan, neon.id)
        dj = opp.create_opportunity(rohan, {
            "event": neon, "title": "Sunset DJ slot (house / disco)",
            "description": "90-minute warm-up set as the sun goes down. CDJ-3000s provided.",
            "opportunity_type": "dj_slot", "compensation_type": "paid",
            "compensation_amount": "15000", "currency": "INR", "capacity": 2,
            "starts_at": day(12, 18), "application_deadline": day(8),
            "location_text": "Lower Parel, Mumbai", "timezone": "Asia/Kolkata",
            "genres": ["electronic"], "skills": ["djing"],
        })
        opp.publish_opportunity(rohan, dj.id)
        band = opp.create_opportunity(rohan, {
            "event": neon, "title": "Live band opener",
            "description": "45-minute set to open the night. Backline provided.",
            "opportunity_type": "band_slot", "compensation_type": "revenue_share", "capacity": 1,
            "starts_at": day(12, 17), "application_deadline": day(9),
            "location_text": "Lower Parel, Mumbai", "timezone": "Asia/Kolkata",
            "genres": ["rock", "indie"],
        })
        opp.publish_opportunity(rohan, band.id)
        jazz = opp.create_opportunity(rohan, {
            "title": "Jazz vocalist for a private dinner",
            "description": "Standards for a 60-guest dinner. Pianist provided. Smart dress.",
            "opportunity_type": "paid_gig", "compensation_type": "paid",
            "compensation_amount": "25000", "currency": "INR", "capacity": 1,
            "starts_at": day(9, 19), "application_deadline": day(6),
            "location_text": "Koramangala, Bengaluru", "timezone": "Asia/Kolkata",
            "genres": ["jazz"], "skills": ["singing"],
        })
        opp.publish_opportunity(rohan, jazz.id)
        audition = opp.create_opportunity(rohan, {
            "title": "Musical theatre ensemble audition",
            "description": "Open call for singers and dancers for a 6-show run.",
            "opportunity_type": "audition", "compensation_type": "negotiable", "capacity": 8,
            "starts_at": day(15, 11), "application_deadline": day(11), "is_online": False,
            "location_text": "Rangashankara, Bengaluru", "timezone": "Asia/Kolkata",
            "genres": ["theatre"], "skills": ["singing", "dancing"],
        })
        opp.publish_opportunity(rohan, audition.id)

        # Applications at every stage of the funnel.
        a1 = opp.submit_application(asha, open_mic.id,
                                    cover_note="I'd play two originals — 'Monsoon Letters' and a new one.",
                                    portfolio_item_ids=[i.id for i in asha.profile.portfolio.all()])
        opp.transition_application(olivia, a1.id, "accepted", reason="Loved the live session!")
        a2 = opp.submit_application(asha, feature.id,
                                    cover_note="Happy to do a full 40 — I have a tight set with loops.")
        opp.transition_application(olivia, a2.id, "shortlisted")
        opp.submit_application(asha, jazz.id, cover_note="Jazz isn't my main thing but I adore standards.")
        opp.submit_application(meera, feature.id,
                               cover_note="Jazz-leaning set with a few indie covers reimagined.")
        opp.submit_application(dev, feature.id, cover_note="We can do an acoustic stripped-down set.")
        opp.submit_application(meera, open_mic.id, cover_note="Two standards, voice and guitar.")
        opp.submit_application(kabir, dj.id, cover_note="Deep, warm house to ease into the night.")
        opp.submit_application(meera, jazz.id, cover_note="Standards are home for me. Rep list attached.")

        # Social graph and posts.
        for follower, followed in [(asha, olivia), (asha, meera), (asha, dev), (meera, asha),
                                   (olivia, asha), (kabir, rohan), (dev, asha), (asha, rohan)]:
            social.follow(follower, followed.id)
        p1 = social.create_post(olivia, body="This Friday at The Loft: 6 open-mic spots, one "
                                "headline set and a host role. Applications close Thursday 🎶")
        p2 = social.create_post(asha, body="New song 'Monsoon Letters' debuts live this Friday. "
                                "Bring an umbrella ☔")
        social.create_post(meera, body="Practising 'Autumn Leaves' in three keys today. The "
                           "difference a semitone makes is wild.")
        social.create_post(dev, body="Rehearsal room smells like coffee and amp dust. Perfect.")
        social.create_post(kabir, body="Sunset sets are the best sets. Change my mind.")
        social.repost(asha, p1.id, body="See you there!")
        for user in (meera, dev, olivia):
            social.like_post(user, p2.id)
        social.add_comment(meera, p2.id, body="Can't wait to hear it live!")
        social.add_comment(olivia, p2.id, body="Front row reserved 🙌")

        # A conversation between the organizer and the booked artist.
        convo, _ = messaging.start_direct_conversation(olivia, asha.id)
        messaging.send_message(olivia, convo.id, body="Hi Asha! You're on the Friday lineup 🎉 "
                               "Sound check at 6:30?")
        messaging.send_message(asha, convo.id, body="Amazing, thank you! 6:30 works. I'll bring "
                               "my loop pedal — is there a power strip near the stage?")
        messaging.send_message(olivia, convo.id, body="Yes, two. And I've shortlisted you for "
                               "the headline set too — deciding by Wednesday.")
        convo2, _ = messaging.start_direct_conversation(meera, asha.id)
        messaging.send_message(meera, convo2.id, body="Want to do a duet at the open mic?")

/** Business types on the public homepage. To use a real photo, change `image`. Copy only describes features the app has. */
export type Business = {
  slug: string;
  name: string;
  image: string;
  tagline: string;
  intro: string;
  ideas: [string, string][];
};

export const BUSINESSES: Business[] = [
  {
    slug: "food",
    name: "Restaurants & Cafes",
    image: "/home/food.svg",
    tagline: "Make people hungry before they walk in.",
    intro: "Share today's specials, behind the scenes kitchen moments and happy tables, and answer questions directly.",
    ideas: [
      ["Reels", "Show a dish being made in under 90 seconds."],
      ["Stories", "Post the day's special. It disappears after 24 hours."],
      ["Messages", "Answer questions about timings and menus in chat."],
    ],
  },
  {
    slug: "fashion",
    name: "Fashion & Retail",
    image: "/home/fashion.svg",
    tagline: "Turn every new arrival into a moment.",
    intro: "Show collections in photo carousels, reveal drops in stories and let customers ask about sizes in a message.",
    ideas: [
      ["Carousels", "Up to 10 photos or videos in one post."],
      ["Highlights", "Keep your best stories on your profile, sorted by collection."],
      ["Live video", "Walk followers through a new collection in real time."],
    ],
  },
  {
    slug: "beauty",
    name: "Beauty & Salons",
    image: "/home/beauty.svg",
    tagline: "Let your results speak for you.",
    intro: "Share transformations and tutorials, and talk to clients one to one before their appointment.",
    ideas: [
      ["Reels", "Short tutorials and before and after videos."],
      ["Hashtags", "Get found by people browsing the looks you do best."],
      ["Video calls", "Talk through a look with a client before they visit."],
    ],
  },
  {
    slug: "fitness",
    name: "Gyms & Fitness",
    image: "/home/fitness.svg",
    tagline: "Build a community that keeps showing up.",
    intro: "Post workouts, go live for group sessions and stay in touch with your members in group chats.",
    ideas: [
      ["Live video", "Run a session for everyone who follows you."],
      ["Group chats", "Keep a batch motivated between classes."],
      ["Insights", "See which of your posts people respond to most."],
    ],
  },
  {
    slug: "travel",
    name: "Travel & Hotels",
    image: "/home/travel.svg",
    tagline: "Sell the view before the booking.",
    intro: "Tag your location, share guest moments and let travellers discover you through places and hashtags.",
    ideas: [
      ["Places", "Tag your location so people searching it can find your posts."],
      ["Reels", "Give a quick tour of a room, a route or a sunset."],
      ["Messages", "Answer travellers' questions directly."],
    ],
  },
  {
    slug: "real-estate",
    name: "Real Estate",
    image: "/home/realestate.svg",
    tagline: "Open the door from anywhere.",
    intro: "Walk buyers through a property on video and take their questions in a call, without a site visit.",
    ideas: [
      ["Video posts", "Share full walkthroughs up to 10 minutes long."],
      ["Video calls", "Show a home live to a buyer in another city."],
      ["Saved posts", "Interested buyers can bookmark a listing to come back to."],
    ],
  },
  {
    slug: "education",
    name: "Education & Coaching",
    image: "/home/education.svg",
    tagline: "Teach something new every day.",
    intro: "Share quick lessons, answer doubts live and keep each batch of students together in one group.",
    ideas: [
      ["Reels", "Explain one idea in 90 seconds."],
      ["Live video", "Hold an open doubt clearing session."],
      ["Group chats", "One group for each batch."],
    ],
  },
  {
    slug: "creators",
    name: "Creators & Artists",
    image: "/home/creators.svg",
    tagline: "Your work deserves a bigger stage.",
    intro: "Publish photos and reels, schedule them in advance and see what your audience responds to.",
    ideas: [
      ["Scheduling", "Save drafts and schedule posts for the right time."],
      ["Insights", "Views, likes, comments and saves for each post."],
      ["Stories", "See who watched them, and keep the best as highlights."],
    ],
  },
];

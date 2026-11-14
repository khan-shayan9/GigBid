// source: synthetic · persona: fullstack_dev · repo: studio-booking
import { prisma } from "./db";
import { enqueueEmail } from "./queue";

const WAITLIST_CUTOFF_HOURS = 6;

export async function cancelBooking(bookingId: string): Promise<void> {
  const booking = await prisma.booking.update({
    where: { id: bookingId },
    data: { status: "cancelled" },
    include: { session: true },
  });

  const hoursLeft = (booking.session.startsAt.getTime() - Date.now()) / 3_600_000;
  if (hoursLeft < WAITLIST_CUTOFF_HOURS) return;

  const next = await prisma.waitlistEntry.findFirst({
    where: { sessionId: booking.sessionId },
    orderBy: { createdAt: "asc" },
  });
  if (!next) return;

  await prisma.$transaction([
    prisma.booking.create({ data: { sessionId: booking.sessionId, memberId: next.memberId } }),
    prisma.waitlistEntry.delete({ where: { id: next.id } }),
  ]);
  await enqueueEmail("waitlist-promoted", next.memberId);
}

import { expect } from "@playwright/test";

export async function chooseKnowledgeBase(page, name) {
  const trigger = page.getByRole("button", { name: "Choose knowledge base", exact: true });
  await trigger.click();
  await page.getByRole("option", { name, exact: true }).click();
  await expect(page.getByRole("dialog", { name: "Choose knowledge base", exact: true })).toHaveCount(0);
  await expect(trigger).toContainText(name === "General chat" ? "Knowledge base" : name);
}

import { describe, expect, it } from "vitest";
import { useState } from "react";
import { fireEvent, render, screen } from "@testing-library/react";
import MultiEmail, { isValidEmail } from "./MultiEmail";

function Harness({ max = 20 }: { max?: number }) {
  const [emails, setEmails] = useState<string[]>([]);
  return <MultiEmail emails={emails} onChange={setEmails} max={max} />;
}

function input(): HTMLInputElement {
  return screen.getByLabelText("Destinatarios") as HTMLInputElement;
}

function type(value: string): void {
  fireEvent.change(input(), { target: { value } });
}

function tags(): HTMLElement[] {
  return screen.queryAllByTestId("email-tag");
}

describe("MultiEmail", () => {
  it("adds a tag on Enter", () => {
    render(<Harness />);
    type("a@tocheck.cl");
    fireEvent.keyDown(input(), { key: "Enter" });
    expect(tags()).toHaveLength(1);
    expect(tags()[0]).toHaveTextContent("a@tocheck.cl");
  });

  it("adds a tag on comma, semicolon and space", () => {
    render(<Harness />);
    type("a@tocheck.cl");
    fireEvent.keyDown(input(), { key: "," });
    type("b@tocheck.cl");
    fireEvent.keyDown(input(), { key: ";" });
    type("c@tocheck.cl");
    fireEvent.keyDown(input(), { key: " " });
    expect(tags()).toHaveLength(3);
  });

  it("marks an invalid email as invalid", () => {
    render(<Harness />);
    type("not-an-email");
    fireEvent.keyDown(input(), { key: "Enter" });
    expect(tags()).toHaveLength(1);
    expect(tags()[0]).toHaveAttribute("data-valid", "false");
    expect(tags()[0]).toHaveClass("invalid");
  });

  it("removes a tag with its × button", () => {
    render(<Harness />);
    type("a@tocheck.cl");
    fireEvent.keyDown(input(), { key: "Enter" });
    expect(tags()).toHaveLength(1);
    fireEvent.click(screen.getByLabelText("Quitar a@tocheck.cl"));
    expect(tags()).toHaveLength(0);
  });

  it("does not add duplicates (case-insensitive)", () => {
    render(<Harness />);
    type("a@tocheck.cl");
    fireEvent.keyDown(input(), { key: "Enter" });
    type("A@Tocheck.CL");
    fireEvent.keyDown(input(), { key: "Enter" });
    expect(tags()).toHaveLength(1);
  });

  it("splits multiple emails on paste", () => {
    render(<Harness />);
    fireEvent.paste(input(), {
      clipboardData: { getData: () => "a@tocheck.cl, b@tocheck.cl; c@tocheck.cl" },
    });
    expect(tags()).toHaveLength(3);
  });

  it("enforces the maximum number of recipients", () => {
    render(<Harness max={2} />);
    fireEvent.paste(input(), {
      clipboardData: { getData: () => "a@x.cl b@x.cl c@x.cl d@x.cl" },
    });
    expect(tags()).toHaveLength(2);
    expect(input()).toBeDisabled();
  });
});

describe("isValidEmail", () => {
  it("accepts well-formed addresses and rejects malformed ones", () => {
    expect(isValidEmail("user@tocheck.cl")).toBe(true);
    expect(isValidEmail("user@sub.tocheck.cl")).toBe(true);
    expect(isValidEmail("bad")).toBe(false);
    expect(isValidEmail("bad@")).toBe(false);
    expect(isValidEmail("bad@domain")).toBe(false);
    expect(isValidEmail("a b@x.cl")).toBe(false);
  });
});
